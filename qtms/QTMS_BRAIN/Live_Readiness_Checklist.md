# QTMS — Live Readiness Checklist

> ⚠️ Live trading is **DISABLED by default** and **not implemented** in this MVP.
> This checklist is the human gate that must be satisfied *before* anyone wires a
> real broker. Satisfying it does NOT promise profit — it only confirms a minimal
> evidence bar and explicit operator consent.

## Hard gates (all enforced in `qtms/app/safety.py`)

- [ ] `QTMSConfig.live.live_trading_enabled = True` (off by default)
- [ ] Environment variable `QTMS_ENABLE_LIVE=true`
- [ ] Environment variable `QTMS_MANUAL_LIVE_APPROVAL` equals the generated approval phrase
- [ ] Validation report passes for the strategies to be traded
- [ ] Paper trading minimum sample size reached (`live.min_paper_trades`)
- [ ] Observed max drawdown ≤ `risk.max_drawdown_pct`
- [ ] Observed risk of ruin ≤ `risk.max_risk_of_ruin`
- [ ] No open **critical** safety violations
- [ ] Kill switch inactive
- [ ] A broker adapter is **explicitly** configured

## Evidence to attach before going live

- [ ] Walk-forward validation across multiple regimes (not one lucky window)
- [ ] Bootstrap confidence interval on expectancy excludes zero
- [ ] Cost-adjusted returns remain positive under stressed slippage/fees
- [ ] Parameter sensitivity is low (strategy is not fragile)
- [ ] Monte Carlo robustness ≥ threshold
- [ ] Learning supervisor `overfitting_risk_score` is low

## Operating rules (never relax)

- Paper trading first. Always.
- No private exchange keys committed to the repo.
- No LLM in the hot trading path. Agent analysis is off-path only.
- Strategies never place orders; everything routes through risk + the order router.
- The kill switch overrides everything.
- Be honest when there is no edge. Most strategies are noise.
