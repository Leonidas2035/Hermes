#!/usr/bin/env python3
"""BTC weekday-seasonality & weekend-sweep study for QuantumEdge.

Tests the owner's thesis: Monday moves are deceptive; true move starts Tuesday
in the opposite direction; weekend range highs/lows get swept Mon+Tue.

Fetches daily OHLCV via a multi-exchange fallback (binance.com is NOT resolvable
from this host — BingX works and is the default). Run:
  ~/QuantumEdge/.venv/bin/python3 scripts/weekday_study.py
"""
import ccxt, datetime as dt
import statistics as st


def get_ex():
    for name in ["bingx", "bybit", "okx", "kraken", "gateio", "kucoin", "mexc"]:
        try:
            e = getattr(ccxt, name)({"enableRateLimit": True})
            e.load_markets()
            print(f"[using exchange: {name}]")
            return e, name
        except Exception as ex:
            print(f"  {name} failed: {str(ex)[:60]}")
    raise SystemExit("no exchange reachable")


ex, exname = get_ex()
sym = "BTC/USDT:USDT" if "BTC/USDT:USDT" in ex.markets else "BTC/USDT"
since = ex.parse8601("2024-06-01T00:00:00Z")
allc = []
while True:
    # SYNC ccxt: fetch_ohlcv returns a list directly — do NOT await.
    c = ex.fetch_ohlcv(sym, timeframe="1d", since=since, limit=1000)
    if not c:
        break
    allc += c
    since = c[-1][0] + 86400000
    if len(c) < 1000:
        break
seen = set(); rows = []
for r in allc:
    if r[0] in seen:
        continue
    seen.add(r[0]); rows.append(r)
rows.sort()


def wd(ts):
    return dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).weekday()


days = [dict(ts=ts, wd=wd(ts), o=o, h=h, l=l, c=c) for ts, o, h, l, c, v in rows]
names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

by_wd = {i: [] for i in range(7)}
for d in days:
    by_wd[d["wd"]].append((d["c"] - d["o"]) / d["o"] * 100)
print("=== Avg daily return (open->close) & %up by weekday (BTC 1d, since 2024-06) ===")
for i in range(7):
    r = by_wd[i]
    up = sum(1 for x in r if x > 0) / len(r) * 100
    print(f"{names[i]}: n={len(r):3d}  avg={st.mean(r):+.3f}%  median={st.median(r):+.3f}%  %up={up:.0f}%")

pairs = []
for k in range(len(days) - 1):
    if days[k]["wd"] == 0 and days[k + 1]["wd"] == 1:
        mon = (days[k]["c"] - days[k]["o"]) / days[k]["o"]
        tue = (days[k + 1]["c"] - days[k + 1]["o"]) / days[k + 1]["o"]
        pairs.append((mon, tue))
opp = sum(1 for m, t in pairs if m * t < 0)
same = sum(1 for m, t in pairs if m * t > 0)
print(f"\n=== Monday close-dir vs Tuesday close-dir (n={len(pairs)}) ===")
print(f"Opposite (Tue reverses Mon): {opp} ({opp/len(pairs)*100:.0f}%)")
print(f"Same direction:              {same} ({same/len(pairs)*100:.0f}%)")
mu = [t for m, t in pairs if m > 0]; md = [t for m, t in pairs if m < 0]
print(f"When Mon UP  (n={len(mu)}): Tue avg={st.mean(mu)*100:+.3f}%  %Tue-down={sum(1 for x in mu if x<0)/len(mu)*100:.0f}%")
print(f"When Mon DOWN(n={len(md)}): Tue avg={st.mean(md)*100:+.3f}%  %Tue-up  ={sum(1 for x in md if x>0)/len(md)*100:.0f}%")

res = dict(total=0, sh=0, sl=0, both=0, fh=0, fl=0)
for k in range(len(days) - 3):
    if days[k]["wd"] == 5 and days[k + 1]["wd"] == 6 and days[k + 2]["wd"] == 0 and days[k + 3]["wd"] == 1:
        wh = max(days[k]["h"], days[k + 1]["h"]); wl = min(days[k]["l"], days[k + 1]["l"])
        mon, tue = days[k + 2], days[k + 3]
        hi = max(mon["h"], tue["h"]); lo = min(mon["l"], tue["l"])
        sh = hi > wh; sl = lo < wl
        res["total"] += 1
        res["sh"] += sh; res["sl"] += sl; res["both"] += (sh and sl)
        if sh and tue["c"] < wh:
            res["fh"] += 1
        if sl and tue["c"] > wl:
            res["fl"] += 1
t = res["total"]
print(f"\n=== Weekend range sweep by Mon+Tue (n={t}) ===")
print(f"Swept weekend HIGH: {res['sh']} ({res['sh']/t*100:.0f}%)")
print(f"Swept weekend LOW:  {res['sl']} ({res['sl']/t*100:.0f}%)")
print(f"Swept BOTH:         {res['both']} ({res['both']/t*100:.0f}%)")
print(f"Swept HIGH -> Tue closed back BELOW (false breakout up):  {res['fh']} ({res['fh']/t*100:.0f}%)")
print(f"Swept LOW  -> Tue closed back ABOVE (false breakdown):    {res['fl']} ({res['fl']/t*100:.0f}%)")

print("\n=== Last 8 Mondays ===")
for d in [d for d in days if d["wd"] == 0][-8:]:
    day = dt.datetime.fromtimestamp(d["ts"] / 1000, dt.timezone.utc).strftime("%Y-%m-%d")
    ret = (d["c"] - d["o"]) / d["o"] * 100
    print(f"{day}: O{d['o']:.0f} H{d['h']:.0f} L{d['l']:.0f} C{d['c']:.0f}  {ret:+.2f}%")

sat = [d for d in days if d["wd"] == 5][-1]; sun = [d for d in days if d["wd"] == 6][-1]
print(f"\nLast weekend range: HIGH={max(sat['h'],sun['h']):.0f}  LOW={min(sat['l'],sun['l']):.0f}")
