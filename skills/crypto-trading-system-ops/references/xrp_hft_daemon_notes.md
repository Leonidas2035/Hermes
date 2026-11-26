# XRP HFT Grid Daemon Notes (QuantumEdge)

Observed 2026-07-31 during order-book cleanup on BingX swap/hedge mode.

## Process signatures
- command: `venv/bin/python3 tools/xrp_hft_daemon.py`
- parent: interactive `/bin/bash -lic`, NOT a systemd/cron service
- PPID/PPID chain is local to the user's session, so `ps` is the reliable source

## Daemon behavior
- Ladder grid around `CENTER=1.0877`, `STEP=0.0006`, `LEVELS=14`, `QTY=1500 XRP`
- Iterates ideal grid every 15 seconds
- Replenishes BOTH missing long-entry buy limits AND short-entry sell limits
- TP shape: attached `takeProfit.triggerPrice/price` dict or standalone SELL limit
- Persists closed orders to `trader_journal.jsonl` in project root

## Why cancels reappear
Cancel-all or manual cancel of XRP sell band followed by a fresh `snapshot` showing
new IDs at the same/adjacent prices is a **respawn event**, not an API bug.

## Safe sequencing with supervisor trading plan
Do NOT cancel until owner/generation source is identified. Preferred order:
1. Identify owner: `ps -p <pid> -o pid,ppid,pgid,command`
2. Check journal/latest lines for evidence it is actively placing orders
3. Choose: suspend/constrain the daemon, or carve allowed bands
4. Cancel external/superfluous orders only while owner is quiesced
5. Verify once more with `snapshot`, paying attention to `open_orders_count` and exact IDs