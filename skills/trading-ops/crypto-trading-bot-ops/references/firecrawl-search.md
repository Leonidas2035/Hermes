# Firecrawl search (news sentiment)

## Request
```
POST https://api.firecrawl.dev/v1/search
Authorization: Bearer <FIRECRAWL_API_KEY>
Content-Type: application/json
{ "query": "XRP Ripple price news today", "limit": 3 }
```

## Response
```json
{ "success": true,
  "data": [ { "url": "...", "title": "...", "description": "..." } ] }
```
On auth failure: `{"success":false,"error":"Unauthorized: Token missing"}`
(means the key var wasn't actually passed — check env).

## Python (no extra deps)
```python
import json, os, urllib.request
key = os.getenv("FIRECRAWL_API_KEY")
req = urllib.request.Request(
    "https://api.firecrawl.dev/v1/search",
    data=json.dumps({"query": f"{SYM.replace('USDT','')} Ripple price news today", "limit": 3}).encode(),
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    method="POST")
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read().decode())
```

## Naive sentiment
Count bull/bear keywords across titles+descriptions:
bull = surge|rise|gain|bull|up|momentum|breakout
bear = drop|fall|bear|down|crash|sell|loss
→ BULLISH if bull>bear, BEARISH if bear>bull, else NEUTRAL.

## Free Tier discipline
- 1 request per analysis, `limit: 3`. Do NOT loop or poll.
- Pass the key via env at launch, not by writing it into `.env`
  (user may restrict editing credential stores).
