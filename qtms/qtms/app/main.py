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
 h3{margin:0 0 4px}
 .sub{color:#7f849c;font-size:12px;margin:2px 0 10px}
 .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;margin-left:8px}
 .paper{background:#1d3a2a;color:#a6e3a1}.live-off{background:#3a1d1d;color:#f38ba8}
 main{padding:24px;display:grid;grid-template-columns:1fr 1fr;gap:16px}
 .card{background:#11151f;border:1px solid #1e2430;border-radius:8px;padding:16px}
 button{background:#1e66f5;color:#fff;border:0;padding:8px 12px;border-radius:6px;cursor:pointer;margin:4px 6px 4px 0;font-size:13px}
 button:hover{background:#3a7bff}
 .warn{color:#f9e2af;font-size:12px;margin-top:8px}
 .result{background:#0b0e14;border:1px solid #1e2430;border-radius:8px;padding:16px;min-height:80px}
 .headline{font-size:20px;font-weight:600;margin-bottom:10px}
 .good{color:#a6e3a1}.bad{color:#f38ba8}.neutral{color:#89b4fa}.muted{color:#7f849c}
 .facts{list-style:none;padding:0;margin:0}
 .facts li{padding:6px 0;border-bottom:1px solid #181c28;display:flex;justify-content:space-between;gap:16px}
 .facts li span:first-child{color:#9399b2}
 .facts li span:last-child{font-weight:600;text-align:right}
 .tag{display:inline-block;background:#1e2430;border-radius:6px;padding:2px 8px;margin:2px;font-size:12px}
 table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
 td,th{padding:6px 8px;border-bottom:1px solid #181c28;text-align:left}
 details{margin-top:12px}summary{cursor:pointer;color:#7f849c;font-size:12px}
 pre{background:#11151f;padding:10px;border-radius:6px;overflow:auto;max-height:240px;font-size:11px}
</style></head><body>
<header><h1>QTMS — Quantum Trading Multi-Layer Stacking
<span class="pill paper">RESEARCH / PAPER</span>
<span class="pill live-off">LIVE DISABLED</span></h1>
<div class="warn" id="statusbar">Loading…</div>
</header>
<main>
 <div class="card"><h3>1 · Data</h3>
  <div class="sub">Synthetic data to experiment, or real market data from a public exchange (read-only).</div>
  <button onclick="act('data','POST','/data/synthetic',{symbol:'BTC/USDT',n:800})">Generate random data</button>
  <button onclick="act('data','POST','/data/synthetic',{symbol:'BTC/USDT',n:1600,drift:0.0012})">Generate trending data</button>
  <button onclick="act('liveData','POST','/data/live',{symbol:'BTC/USDT',timeframe:'5m',limit:1000})">Fetch live data (real market)</button></div>
 <div class="card"><h3>2 · Test a strategy</h3>
  <div class="sub">Validate one strategy and stress-test it with Monte Carlo.</div>
  <button onclick="act('backtest','POST','/backtest/run',{symbol:'BTC/USDT',strategy:'trend_following'})">Validate trend strategy</button>
  <button onclick="act('mc','POST','/monte-carlo/run',{symbol:'BTC/USDT',strategy:'mean_reversion',n_paths:200})">Monte Carlo</button></div>
 <div class="card"><h3>3 · Paper trade</h3>
  <div class="sub">Run virtual trades — no real money. Start, then step forward.</div>
  <button onclick="act('paperStart','POST','/paper/start',{symbol:'BTC/USDT',warmup:150})">Start</button>
  <button onclick="act('paperStep','POST','/paper/step',{steps:25})">Step forward x25</button>
  <button onclick="act('paperStatus','GET','/paper/status')">Status</button>
  <button onclick="act('paperTrades','GET','/paper/trades')">Trades</button>
  <button onclick="act('paperStatus','POST','/paper/stop')">Stop</button></div>
 <div class="card"><h3>4 · Learning agent</h3>
  <div class="sub">The agent searches strategies and only "promotes" what survives unseen data.</div>
  <button onclick="act('analyze','POST','/agents/learning/analyze',{symbol:'BTC/USDT'})">Analyze results</button>
  <button onclick="act('discover','POST','/agents/learning/discover',{symbol:'BTC/USDT'})">Discover &amp; promote</button>
  <button onclick="act('promotion','GET','/agents/learning/promotion')">Latest promotion</button>
  <div class="warn">Promotion = survived an unseen test once. NOT a profit promise.</div></div>
 <div class="card" style="grid-column:1/3"><h3>5 · Autopilot <span class="muted" style="font-size:12px">(autonomous research — paper only)</span></h3>
  <div class="sub">Runs the loop by itself: refresh data → discover → paper-trade → analyze, on repeat. Promotions are surfaced for your approval. Never goes live; kill switch stops it.</div>
  <button onclick="startAuto('synthetic')">▶ Start (synthetic)</button>
  <button onclick="startAuto('live')">▶ Start on LIVE data</button>
  <button onclick="stopAuto()">⏹ Stop</button>
  <button onclick="act('autopilot','POST','/autopilot/approve')">✔ Approve latest promotion</button>
  <div class="result" id="autopilot" style="margin-top:10px"><span class="muted">Autopilot is idle.</span></div></div>
 <div class="card" style="grid-column:1/3"><h3>Result</h3>
  <div class="result" id="out"><span class="muted">Pick an action above. Tip: do them in order 1 → 2 → 3 → 4.</span></div></div>
</main>
<script>
const pct=x=>(x==null||isNaN(x))?'—':(x*100).toFixed(1)+'%';
const n2=(x,d=2)=>(x==null||isNaN(x))?'—':Number(x).toFixed(d);
const money=x=>(x==null||isNaN(x))?'—':'$'+Number(x).toLocaleString(undefined,{maximumFractionDigits:2});
const cls=ok=>ok?'good':'bad';
function robust(x){if(x>=0.7)return'strong';if(x>=0.5)return'moderate';return'weak';}
function facts(rows){return '<ul class="facts">'+rows.map(r=>`<li><span>${r[0]}</span><span class="${r[2]||''}">${r[1]}</span></li>`).join('')+'</ul>';}
function head(txt,c){return `<div class="headline ${c||'neutral'}">${txt}</div>`;}
function raw(d){return `<details><summary>show raw data</summary><pre>${JSON.stringify(d,null,2)}</pre></details>`;}

const R={
 data:d=>head(`Generated ${d.rows} candles of ${d.symbol}`,'neutral')+facts([
   ['Last price',money(d.last_close)],
   ['Data robustness',n2((d.data_robustness||{}).robustness_score,2)+' ('+robust((d.data_robustness||{}).robustness_score)+')'],
   ['Data quality',pct((d.data_robustness||{}).data_quality_score)]])+
   '<div class="warn">Now try step 2 or jump to step 4.</div>'+raw(d),
 backtest:d=>{const m=d.metrics||{};return head(d.strategy+' — '+(d.passed?'PASSED ✅':'DID NOT PASS ❌'),cls(d.passed))+facts([
   ['Trades',m.n_trades],
   ['Total return (after costs)',pct(m.total_return),cls(m.total_return>0)],
   ['Win rate',pct(m.win_rate)],
   ['Profit factor',n2(m.profit_factor)],
   ['Max drawdown',pct(m.max_drawdown),'bad'],
   ['Score',n2(d.score)]])+
   (d.fail_reasons&&d.fail_reasons.length?'<div class="warn">Why it failed: '+d.fail_reasons.join('; ')+'</div>':'<div class="warn good">Cleared every validation gate.</div>')+raw(d);},
 mc:d=>{const m=d.monte_carlo||{};return head('Monte Carlo · '+d.strategy,'neutral')+facts([
   ['Robustness',n2(m.robustness_score)+' ('+robust(m.robustness_score)+')',cls(m.robustness_score>=0.5)],
   ['Chance of positive expectancy',pct(m.prob_positive_expectancy)],
   ['Risk of ruin',pct(m.risk_of_ruin),cls(m.risk_of_ruin<=0.05)],
   ['Worst-case drawdown (95%)',pct(m.max_drawdown_p95),'bad'],
   ['Survives higher costs',pct(m.cost_survival)],
   ['Trades',m.n_trades]])+raw(d);},
 paperStart:d=>head('Paper session started','good')+facts([
   ['Symbol',d.symbol],['Candles loaded',d.n_candles],['Starting at bar',d.start_idx]])+
   '<div class="warn">Now press "Step forward x25".</div>'+raw(d),
 paperStep:d=>{const l=d.last||{};return head(`Stepped forward ${d.steps} bars`,'neutral')+facts([
   ['Equity now',money(l.equity)],
   ['Last decision',l.approved==null?'no decision':(l.approved?'TRADE':'stood aside')],
   ['Conviction',l.conviction==null?'—':n2(l.conviction)],
   ['Events',(l.events&&l.events.length)?l.events.join(', '):'none']])+
   '<div class="warn">On random data the system usually stands aside — that is the honest default.</div>'+raw(d);},
 paperStatus:d=>head(d.running?'Paper engine running':'Paper engine stopped',d.running?'good':'muted')+facts([
   ['Equity',money(d.equity)],['Cash',money(d.cash)],
   ['Open positions',Object.keys(d.open_positions||{}).length],
   ['Closed trades',d.n_trades],['Decisions made',d.n_decisions]])+raw(d),
 paperTrades:d=>{const t=d.trades||[];if(!t.length)return head('No closed trades yet','muted')+'<div class="warn">The system only trades when conviction passes the gate.</div>';
   return head(`${t.length} closed trades`,'neutral')+'<table><tr><th>Symbol</th><th>Side</th><th>PnL</th><th>Return</th></tr>'+
   t.map(x=>`<tr><td>${x.symbol}</td><td>${x.direction}</td><td class="${cls(x.pnl>0)}">${money(x.pnl)}</td><td>${pct(x.pnl_pct)}</td></tr>`).join('')+'</table>'+raw(d);},
 analyze:d=>head('Analysis complete','neutral')+facts([
   ['Overfitting risk',n2(d.overfitting_risk_score)+(d.overfitting_risk_score>=0.6?' (high)':' (ok)'),cls(d.overfitting_risk_score<0.6)],
   ['Proposes disabling',(d.propose_disable||[]).join(', ')||'none'],
   ['Parameter proposals',(d.parameter_proposals||[]).length],
   ['Risk proposals',(d.risk_proposals||[]).length],
   ['Can enable live?',d.can_enable_live?'YES':'NO (locked)','good']])+
   '<div class="warn">All proposals need your manual approval. The agent never trades live.</div>'+raw(d),
 liveData:d=>{ if(!d.ok) return head('Live data unavailable','bad')+'<div class="warn bad">'+d.error+'</div><div class="warn">'+(d.hint||'')+'</div>';
   return head('Live data · '+d.symbol+' · '+d.source,'good')+facts([
     ['Rows',d.rows],['Last price',money(d.last_close)],['Timeframe',d.timeframe],
     ['From',d.first_time],['To',d.last_time],['Data quality',pct(d.data_quality)]])+
     '<div class="warn">Real market data loaded ✅. Now run step 2/4, or start the autopilot on LIVE.</div>'+raw(d);},
 discover:d=>renderPromotion(d),
 promotion:d=>renderPromotion(d),
 autopilot:d=>{ pollAuto(); const ok=d.approved?'good':'muted'; return head('Approval',ok)+'<div class="warn '+ok+'">'+(d.note||'')+'</div>'; }
};
function renderAuto(d){
 const last=d.last_summary||{};
 const pend=(d.pending_approvals||[]).length;
 let html=head(d.running?`Autopilot running · cycle ${d.cycle}`:`Autopilot stopped · ${d.cycle} cycles done`,d.running?'good':'muted');
 html+=facts([
   ['Status',d.running?'RUNNING':'stopped',d.running?'good':'muted'],
   ['Symbol',d.symbol],
   ['Data source',(d.data_source||'synthetic')+(d.data_source=='live'?' '+(d.timeframe||''):''),d.data_source=='live'?'good':'muted'],
   ['Last cycle verdict',last.promoted==null?'—':(last.promoted?'PROMOTED ✅':'no edge found'),last.promoted?'good':'muted'],
   ['Last paper equity',last.paper_equity==null?'—':money(last.paper_equity)],
   ['Promotions awaiting approval',pend,pend?'good':'muted'],
   ['Approved (paper only)',d.n_approved],
   ['Can enable live?','NO (locked)','good']]);
 if(pend){const p=d.pending_approvals[d.pending_approvals.length-1];
   html+='<div class="warn good">Pending: '+(p.survivors||[]).join(', ')+' — holdout return '+pct((p.holdout_metrics||{}).total_return)+'. Click "Approve latest promotion" to accept (paper only).</div>';}
 if(d.last_error)html+='<div class="warn bad">last error: '+d.last_error+'</div>';
 html+='<div class="warn">Autonomous research only · paper money · live disabled · kill switch overrides.</div>';
 return html;
}
let _autoTimer=null;
async function pollAuto(){
 try{const d=await(await fetch('/autopilot/status')).json();
   document.getElementById('autopilot').innerHTML=renderAuto(d);
   if(!d.running&&_autoTimer){clearInterval(_autoTimer);_autoTimer=null;}
 }catch(e){}
}
async function startAuto(src){
 src=src||'synthetic';
 const el=document.getElementById('autopilot');el.innerHTML='<span class="muted">Starting autopilot ('+src+')…</span>';
 const body=(src==='live')
   ?{symbol:'BTC/USDT',interval_seconds:30,data_source:'live',timeframe:'5m',source:'auto',drift:0}
   :{symbol:'BTC/USDT',interval_seconds:20,drift:0.0008};
 await fetch('/autopilot/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!_autoTimer)_autoTimer=setInterval(pollAuto,4000);
 pollAuto();
}
async function stopAuto(){
 await fetch('/autopilot/stop',{method:'POST'});
 if(_autoTimer){clearInterval(_autoTimer);_autoTimer=null;}
 pollAuto();
}
function renderPromotion(d){
 if(d.note&&d.promoted==null) return head('No discovery run yet','muted')+'<div class="warn">'+d.note+'</div>';
 const m=d.holdout_metrics||{};
 return head(d.promoted?'PROMOTED ✅':'NOT promoted ❌',cls(d.promoted))+facts([
   ['Candidates evaluated',d.candidates_evaluated],
   ['Survivors',(d.survivors||[]).map(s=>s.name).join(', ')||'none'],
   ['Ensemble weights',Object.entries(d.weights||{}).map(([k,v])=>`${k} ${(v*100).toFixed(0)}%`).join('  ')||'—'],
   ['Return on UNSEEN data',pct(m.total_return),cls(m.total_return>0)],
   ['Trades (unseen)',m.n_trades],
   ['Max drawdown (unseen)',pct(m.max_drawdown),'bad'],
   ['Robustness (unseen)',n2(m.mc_robustness)]])+
   '<div class="warn">'+((d.reasons||[]).join('; '))+'. Promotion ≠ profit guarantee — keep paper trading.</div>'+raw(d);
}

async function act(kind,method,url,body){
 const el=document.getElementById('out');
 el.innerHTML='<span class="muted">Running… (Monte Carlo / discovery can take a few seconds)</span>';
 const opt={method,headers:{'Content-Type':'application/json'}};
 if(body)opt.body=JSON.stringify(body);
 try{
   const r=await fetch(url,opt);const d=await r.json();
   el.innerHTML=(R[kind]?R[kind](d):JSON.stringify(d,null,2));
 }catch(e){el.innerHTML='<span class="bad">Error: '+e+'</span>';}
}
async function refreshStatus(){
 try{const d=await(await fetch('/health')).json();
   document.getElementById('statusbar').innerHTML=
   `⚠️ No profit promised · Mode: <b>${d.mode}</b> · Live trading: <b class="bad">${d.live_trading_enabled?'ON':'OFF'}</b> · Kill switch: <b>${d.kill_switch?'ACTIVE':'inactive'}</b>`;
 }catch(e){}
}
refreshStatus();
</script></body></html>
"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_alias():
    return DASHBOARD_HTML
