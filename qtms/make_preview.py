"""Generate a self-contained offline preview of the QTMS dashboard.

Takes the real DASHBOARD_HTML and injects a mock fetch() layer + a DEMO banner
so it works with no server (open the file directly on a phone). Keeps the UI in
sync with the real app since it reuses the same HTML.
"""
import re
from pathlib import Path

from qtms.app.main import DASHBOARD_HTML

MOCK = r"""
<div style="background:#3a2d1d;color:#f9e2af;padding:7px 12px;font-size:12px;text-align:center">
📱 PREVIEW / DEMO MODE — sample data, no server. The real app connects to your QTMS engine.</div>
<script>
(function(){
 const J=d=>({json:async()=>d,text:async()=>JSON.stringify(d)});
 const coins=["BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","XRP/USDT","DOGE/USDT","ADA/USDT","TRX/USDT","AVAX/USDT","LINK/USDT"];
 const A={running:false,cycle:0,symbols:coins.slice(),scoreboard:{},pending:[],approved:0,last:null};
 function lb(){return Object.entries(A.scoreboard).map(([s,v])=>({symbol:s,cycles:v.cycles,promotions:v.promotions,best_return:v.best_return,strategies:v.strategies})).sort((a,b)=>b.promotions-a.promotions||b.best_return-a.best_return);}
 function advance(){
   A.cycle++;
   const sym=A.symbols[(A.cycle-1)%A.symbols.length];
   const sb=A.scoreboard[sym]||(A.scoreboard[sym]={cycles:0,promotions:0,best_return:0,strategies:{}});
   sb.cycles++;
   const promoted=Math.random()<0.30;
   if(promoted){sb.promotions++;const r=0.05+Math.random()*0.18;sb.best_return=Math.max(sb.best_return,r);
     const st=Math.random()<0.5?'trend_following':'breakout';sb.strategies[st]=(sb.strategies[st]||0)+1;
     A.pending.push({symbol:sym,survivors:['trend_following','breakout'],holdout_metrics:{total_return:r,max_drawdown:0.08,n_trades:40,mc_robustness:0.94},done:false});}
   A.last={symbol:sym,promoted:promoted,paper_equity:10000+(Math.random()*60-30)};
 }
 function statusObj(){return {running:A.running,cycle:A.cycle,symbol:A.symbols[0]+' +'+(A.symbols.length-1)+' more',symbols:A.symbols,last_symbol:A.last?A.last.symbol:null,data_source:'synthetic',timeframe:'5m',last_summary:A.last?{promoted:A.last.promoted,paper_equity:A.last.paper_equity}:{},pending_approvals:A.pending.filter(x=>!x.done),n_approved:A.approved,leaderboard:lb(),can_enable_live:false,last_error:null};}
 const promo={symbol:'BTC/USDT',promoted:true,candidates_evaluated:30,survivors:[{name:'trend_following'},{name:'breakout'}],weights:{trend_following:0.52,breakout:0.48},holdout_metrics:{total_return:0.149,max_drawdown:0.083,n_trades:43,mc_robustness:0.95},reasons:['passed all unseen-holdout gates'],can_enable_live:false};
 const data={
   '/health':()=>({status:'ok',mode:'paper/research',live_trading_enabled:false,kill_switch:false}),
   '/symbols':()=>({symbols:coins}),
   '/data/synthetic':b=>({symbol:b.symbol,rows:b.n||800,last_close:30150.2,data_robustness:{robustness_score:0.99,data_quality_score:1.0}}),
   '/data/live':b=>({ok:true,symbol:b.symbol,source:'binance(demo)',timeframe:'5m',rows:1000,last_close:64210.5,first_time:'2024-06-01 00:00',last_time:'2024-06-04 11:25',data_quality:1.0}),
   '/backtest/run':b=>({symbol:b.symbol,strategy:b.strategy,passed:false,score:0.58,metrics:{n_trades:24,total_return:0.031,win_rate:0.46,profit_factor:1.12,max_drawdown:0.066,expectancy:0.0012,avg_win:0.02,avg_loss:-0.015},fail_reasons:['sample too small: 24 < 30 trades']}),
   '/monte-carlo/run':b=>({symbol:b.symbol,strategy:b.strategy,monte_carlo:{robustness_score:0.44,prob_positive_expectancy:0.11,risk_of_ruin:0.01,max_drawdown_p95:0.41,cost_survival:0.0,signal_persistence:0.78,n_trades:95}}),
   '/paper/start':b=>({symbol:b.symbol,start_idx:150,n_candles:800}),
   '/paper/step':()=>({steps:25,last:{idx:175,equity:10000,events:[],approved:false,conviction:0.21}}),
   '/paper/status':()=>({running:true,equity:10000,cash:9998.6,n_trades:0,n_decisions:25,open_positions:{},starting_balance:10000}),
   '/paper/stop':()=>({running:false,equity:10000,cash:10000,n_trades:0,n_decisions:25,open_positions:{},starting_balance:10000}),
   '/paper/trades':()=>({trades:[]}),
   '/agents/learning/analyze':b=>({symbol:b.symbol,overfitting_risk_score:0.83,propose_disable:['mean_reversion','liquidity_sweep','statistical_arbitrage'],parameter_proposals:[1,2,3,4,5,6],risk_proposals:[1],can_enable_live:false,requires_manual_approval:true}),
   '/agents/learning/meta-model':b=>({available:true,model:'logistic_regression (walk-forward)',horizon_bars:3,folds_used:4,n_samples:780,oos_auc_mean:0.508,oos_auc_min:0.491,oos_accuracy_mean:0.512,has_edge:false,top_features:[{feature:'vwap_dist',weight:0.31},{feature:'slope',weight:0.27},{feature:'momentum',weight:0.22}],verdict:'no reliable edge (coin flip) - honest null result',symbol:b.symbol}),
   '/scheduler/status':()=>({running:false,interval_hours:24,data_source:'live',days_per_run:1,last_run:'2026-06-23T08:00',next_due:'2026-06-24T08:00',n_runs:5,history_len:5,can_enable_live:false,last_error:null,consensus:{trend_following:{verdict:'KEEP',runs:5,keep:5,improve:0,erase:0,stability:1.0},breakout:{verdict:'KEEP',runs:5,keep:4,improve:1,erase:0,stability:0.8},momentum:{verdict:'KEEP',runs:5,keep:4,improve:1,erase:0,stability:0.8},macd_trend:{verdict:'IMPROVE',runs:5,keep:1,improve:3,erase:1,stability:0.6},mean_reversion:{verdict:'ERASE',runs:5,keep:0,improve:1,erase:4,stability:0.8},rsi_reversion:{verdict:'ERASE',runs:5,keep:0,improve:0,erase:5,stability:1.0}}}),
   '/scheduler/start':()=>({running:true,interval_hours:24,data_source:'live'}),
   '/scheduler/stop':()=>({running:false}),
   '/scheduler/run-now':()=>({ran:true,verdicts:{trend_following:'KEEP',mean_reversion:'ERASE'},consensus:{}}),
   '/scheduler/apply-consensus':()=>({applied:true,erased:['mean_reversion','rsi_reversion'],active_now:['trend_following','breakout','momentum','donchian_breakout','macd_trend'],note:'Applied to PAPER research config only. Live trading still disabled.'}),
   '/agents/campaign/run':b=>({days:b.days||3,mode:'PAPER (no real money)',data_source:'synthetic',total_runs:30,total_promotions:7,promotion_rate:0.233,can_enable_live:false,note:'Verdicts are evidence-based over a simulated multi-day paper test.',recommendations:{keep:['breakout','donchian_breakout','momentum','trend_following'],improve:['macd_trend'],erase:['mean_reversion','volatility_expansion','liquidity_sweep','statistical_arbitrage','rsi_reversion','bollinger_bounce','vwap_reversion']},strategy_scorecards:[{strategy:'breakout',verdict:'KEEP',validation_pass_rate:0.33,promotion_contribution_rate:0.20,avg_robustness:0.67},{strategy:'donchian_breakout',verdict:'KEEP',validation_pass_rate:0.37,promotion_contribution_rate:0.20,avg_robustness:0.72},{strategy:'momentum',verdict:'KEEP',validation_pass_rate:0.40,promotion_contribution_rate:0.17,avg_robustness:0.74},{strategy:'trend_following',verdict:'KEEP',validation_pass_rate:0.27,promotion_contribution_rate:0.10,avg_robustness:0.82},{strategy:'macd_trend',verdict:'IMPROVE',validation_pass_rate:0.10,promotion_contribution_rate:0.0,avg_robustness:0.64},{strategy:'mean_reversion',verdict:'ERASE',validation_pass_rate:0.0,promotion_contribution_rate:0.0,avg_robustness:0.47},{strategy:'rsi_reversion',verdict:'ERASE',validation_pass_rate:0.0,promotion_contribution_rate:0.0,avg_robustness:0.50}]}),
   '/agents/learning/discover':b=>Object.assign({},promo,{symbol:b.symbol}),
   '/agents/learning/promotion':()=>promo,
   '/autopilot/start':b=>{A.running=true;if(b&&b.symbols&&b.symbols.length)A.symbols=b.symbols;return{running:true,symbol:A.symbols[0]+' +'+(A.symbols.length-1)+' more',interval_seconds:20};},
   '/autopilot/stop':()=>{A.running=false;return statusObj();},
   '/autopilot/status':()=>{if(A.running)advance();return statusObj();},
   '/autopilot/approve':()=>{const p=A.pending.filter(x=>!x.done);if(p.length){p[p.length-1].done=true;A.approved++;return{approved:p[p.length-1],note:'approved for PAPER use only; live still disabled'};}return{approved:null,note:'no pending promotions to approve'};},
   '/autopilot/reset-leaderboard':()=>{A.scoreboard={};A.pending=[];A.approved=0;A.cycle=0;return{reset:true};},
 };
 window.fetch=function(url,opt){opt=opt||{};let b={};try{if(opt.body)b=JSON.parse(opt.body);}catch(e){}
   for(const k in data){if(url.indexOf(k)>=0)return Promise.resolve(J(data[k](b)));}
   return Promise.resolve(J({note:'preview:'+url}));};
})();
</script>
"""


def build() -> str:
    html = DASHBOARD_HTML
    # Manifest/icon links point at server routes that won't exist offline; drop them.
    html = html.replace('<link rel="manifest" href="/manifest.json">', "")
    html = re.sub(r'<link rel="(apple-touch-icon|icon)"[^>]*>', "", html)
    # Inject the DEMO banner + mock fetch right after <body> so it runs first.
    html = html.replace("<body>", "<body>" + MOCK, 1)
    return html


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "preview.html"
    out.write_text(build(), encoding="utf-8")
    print("wrote", out, len(build()), "bytes")
