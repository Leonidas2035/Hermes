import json, os, numpy as np
from dotenv import load_dotenv
load_dotenv("/home/layman/QuantumEdge/.env")
import ccxt

sym = ccxt.bingx({"enableRateLimit": True, "timeout": 25000})
if str(os.getenv("USE_TESTNET","1")).lower() in {"1","true","t"}:
    sym.set_sandbox_mode(True)

def ind(ohlc):
    c = np.array([x[4] for x in ohlc], float)
    n = len(c)
    rsi = None
    if n >= 15:
        d = np.diff(c); g = np.where(d>0,d,0.0); l = np.where(d<0,-d,0.0)
        ag = g[-14:].mean(); al = l[-14:].mean()
        rsi = 100 - 100/(1+(ag/al if al else 99))
    def ema(a,span):
        k=2/(span+1); out=np.empty_like(a,float); out[0]=a[0]
        for i in range(1,len(a)): out[i]=a[i]*k+out[i-1]*(1-k)
        return out
    ml=ms=mh=None
    if n>=35:
        e12=ema(c,12); e26=ema(c,26); m=e12-e26; sig=ema(m,9)
        ml=float(m[-1]); ms=float(sig[-1]); mh=float(m[-1]-sig[-1])
    bl=bm=bu=None
    if n>=20:
        w=c[-20:]; ma=w.mean(); sd=w.std(); bm=float(ma); bu=float(ma+2*sd); bl=float(ma-2*sd)
    atr=None
    if len(ohlc)>=15:
        hp=np.array([x[2] for x in ohlc],float); lp=np.array([x[3] for x in ohlc],float)
        tr=np.maximum(hp[1:]-lp[1:], np.abs(hp[1:]-c[:-1]), np.abs(lp[1:]-c[:-1]))
        atr=float(np.mean(tr[-14:]))
    return rsi,ml,ms,mh,bl,bm,bu,atr

def fetch(symbol,tf):
    try:
        o = sym.fetch_ohlcv(symbol,tf,limit=200)
        rsi,ml,ms,mh,bl,bm,bu,atr = ind(o)
        last=float(o[-1][4])
        return f"{symbol} {tf}", {
            "last":round(last,5),
            "rsi14":round(rsi,2) if rsi is not None else None,
            "macd_line":round(ml,6) if ml is not None else None,
            "macd_signal":round(ms,6) if ms is not None else None,
            "macd_hist":round(mh,6) if mh is not None else None,
            "bb_low":round(bl,5) if bl is not None else None,
            "bb_mid":round(bm,5) if bm is not None else None,
            "bb_up":round(bu,5) if bu is not None else None,
            "atr":round(atr,6) if atr is not None else None,
            "atr_pct":round(atr/last*100,3) if atr is not None else None,
        }
    except Exception as e:
        return f"{symbol} {tf}", {"error":str(e)[:200]}

res = {}
for s,t in [("XRP/USDT:USDT","1h"),("XRP/USDT:USDT","5m"),("BTC/USDT:USDT","1h")]:
    k,v = fetch(s,t); res[k]=v
print(json.dumps(res, indent=2))
