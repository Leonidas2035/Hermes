# BingX Hedge-Mode ccxt Gotchas (QuantumEdge / testnet VST)

Reproduced and fixed 2026-07-31 while operating QuantumEdge on BingX testnet
(`tools/qe_trade.py`). Two independent bugs made every SHORT-path operation
fail with `bingx {"code":101205,"msg":"No position to close","data":{}}` and
made the supervisor blind to SHORT hedges.

## Gotcha 1 — `fetch_positions(symbols=[...])` hides SHORT legs
In hedge mode, the symbol-filtered fetch returns ONLY the LONG position for
that symbol. Any SHORT leg is silently dropped. Result:
- `snapshot`/`close`/`set_sl` logic that filters the returned list never sees a
  SHORT -> "No position to close" even when a real short exists.
- The supervisor can believe a hedge is intact while the exchange already
  force-liquidated it (the bug masked a real ~20k VST drawdown this session).

REPRO:
```python
ps = await ex.fetch_positions(symbols=[sym])   # returns only LONG
print([(p['symbol'], p['side']) for p in ps])  # ['SOL/USDT:USDT', 'long']  (short missing!)
```

FIX — fetch unfiltered, filter client-side by `info.positionSide`:
```python
async def _fetch_positions_all(ex):
    # BingX testnet hedge mode: symbol-filtered fetch hides SHORT legs.
    return await ex.fetch_positions()

def _find_pos(ps, symbol, side=None):
    base = symbol.upper().replace("/USDT:USDT","").replace("/USDT","").replace("USDT","").replace(":","")
    out = []
    for p in ps:
        s = (p.get("symbol") or "").split(":")[0].replace("/USDT","")
        if s != base and base not in s:
            continue
        if side and (p.get("info",{}) or {}).get("positionSide","").upper() != side.upper():
            continue
        out.append(p)
    return out
```

## Gotcha 2 — SHORT order direction is inverted from the verb
BingX reads the order SIDE + `positionSide` together:
- OPEN short  -> `side="sell"`, `params={"positionSide":"SHORT"}`
- CLOSE short -> `side="buy"`,  `params={"positionSide":"SHORT"}`

Sending `buy` + `positionSide=SHORT` (a natural "buy SHORT") is interpreted as
*close-short* and returns `101205` when no short exists yet. That was the exact
failure of `qe_trade.py place buy SHORT` / `market buy SHORT`.

FIX in the CLI — keep the caller's verb for `is_closing`/guardrails, but flip
the side sent to the exchange for SHORT legs:
```python
ex_side = side.lower()
if pos_side.upper() == "SHORT":
    ex_side = "sell" if side.lower() == "buy" else "buy"
o = await ex.create_order(symbol, "market", ex_side, qty, params={"positionSide": pos_side.upper()})
```

## Verification (real testnet, venv)
```bash
cd /home/layman/.hermes/quantumedge_analysis
./venv/bin/python3 tools/qe_trade.py market buy SHORT 1 SOLUSDT   # opens (side=sell)
./venv/bin/python3 tools/qe_trade.py market sell SHORT 1 SOLUSDT  # closes (side=buy)
./venv/bin/python3 tools/qe_trade.py snapshot                     # 4 legs visible
```
Both open/close must return `status: closed` with NO `101205`. (Use the project
venv — system `python3` lacks `ccxt` and gives a false ModuleNotFoundError.)
