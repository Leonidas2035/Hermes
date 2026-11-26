import json, os

journal_path = "/home/layman/.hermes/quantumedge_analysis/runtime/trade_journal.jsonl"
if not os.path.exists(journal_path):
    print("No journal found")
    exit()

xrp_closes = 0
xrp_profit = 0.0

with open(journal_path, "r") as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get("symbol") == "XRP/USDT:USDT" and data.get("act") == "close":
                xrp_closes += 1
                profit = float(data.get("realized_pnl", 0))
                xrp_profit += profit
        except:
            pass

print(f"Journal XRP Closes: {xrp_closes}")
print(f"Journal XRP Profit: {xrp_profit}")
