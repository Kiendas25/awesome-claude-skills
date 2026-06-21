"""QTMS FastAPI entrypoint + a minimal HTML dashboard.

Run:  uvicorn qtms.app.main:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ..dashboard.api_routes import router
from .config import get_config
from .safety import KILL_SWITCH

app = FastAPI(
    title="QTMS — Quantum Trading Multi-Layer Stacking Operation",
    description=(
        "Local-first, paper-trading-first research system. Live trading is "
        "DISABLED by default. No profit is promised; most strategies are noise."
    ),
    version="0.1.0",
)
app.include_router(router)


DASHBOARD_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>QTMS Dashboard</title>
<style>
 body{font-family:system-ui,Arial;margin:0;background:#0b0e14;color:#cdd6f4}
 header{padding:16px 24px;background:#11151f;border-bottom:1px solid #1e2430}
 h1{font-size:18px;margin:0}
 .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;margin-left:8px}
 .paper{background:#1d3a2a;color:#a6e3a1}.live-off{background:#3a1d1d;color:#f38ba8}
 main{padding:24px;display:grid;grid-template-columns:1fr 1fr;gap:16px}
 .card{background:#11151f;border:1px solid #1e2430;border-radius:8px;padding:16px}
 button{background:#1e66f5;color:#fff;border:0;padding:8px 12px;border-radius:6px;cursor:pointer;margin:4px 0}
 pre{background:#0b0e14;padding:10px;border-radius:6px;overflow:auto;max-height:260px;font-size:12px}
 .warn{color:#f9e2af;font-size:12px}
</style></head><body>
<header><h1>QTMS — Quantum Trading Multi-Layer Stacking
<span class="pill paper">RESEARCH / PAPER</span>
<span class="pill live-off">LIVE DISABLED</span></h1>
<div class="warn">⚠️ No profit promised. Synthetic data. No real funds. Live trading gated &amp; off by default.</div>
</header>
<main>
 <div class="card"><h3>System</h3>
  <button onclick="call('GET','/health','health')">Health</button>
  <button onclick="call('POST','/data/synthetic','out',{symbol:'BTC/USDT',n:800})">Generate Data</button>
  <button onclick="call('POST','/live/disabled-status','out')">Live Status</button>
  <pre id="health"></pre></div>
 <div class="card"><h3>Backtest / Validation</h3>
  <button onclick="call('POST','/backtest/run','out',{symbol:'BTC/USDT',strategy:'trend_following'})">Validate Trend</button>
  <button onclick="call('POST','/monte-carlo/run','out',{symbol:'BTC/USDT',strategy:'mean_reversion',n_paths:200})">Monte Carlo</button></div>
 <div class="card"><h3>Paper Trading</h3>
  <button onclick="call('POST','/paper/start','out',{symbol:'BTC/USDT',warmup:150})">Start</button>
  <button onclick="call('POST','/paper/step','out',{steps:25})">Step x25</button>
  <button onclick="call('GET','/paper/status','out')">Status</button>
  <button onclick="call('GET','/paper/trades','out')">Trades</button>
  <button onclick="call('POST','/paper/stop','out')">Stop</button></div>
 <div class="card"><h3>Learning Supervisor (off-path)</h3>
  <button onclick="call('POST','/agents/learning/analyze','out',{symbol:'BTC/USDT'})">Analyze</button>
  <button onclick="call('GET','/agents/learning/latest','out')">Latest Reco</button></div>
 <div class="card" style="grid-column:1/3"><h3>Output</h3><pre id="out">Click a button…</pre></div>
</main>
<script>
async function call(method,url,target,body){
 const el=document.getElementById(target);el.textContent='…';
 const opt={method,headers:{'Content-Type':'application/json'}};
 if(body)opt.body=JSON.stringify(body);
 try{const r=await fetch(url,opt);el.textContent=JSON.stringify(await r.json(),null,2);}
 catch(e){el.textContent='error: '+e;}
}
call('GET','/health','health');
</script></body></html>
"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_alias():
    return DASHBOARD_HTML
