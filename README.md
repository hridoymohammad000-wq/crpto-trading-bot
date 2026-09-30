# Crypto Intraday Bot — Work Checklist

## Workflow Rule

- One task at a time.
- Fix locally.
- Run tests and production build.
- Verify in UI/runtime.
- Only after verification, change [ ] to [x].
- Then commit + push.
- Then move to next task.

---

## Completed — 29–30 Sep 2026

- [x] Bybit Demo retCode 10002 timestamp handling
- [x] /account stability test 20/20 passed
- [x] Daily PnL changed to today's realized closed-trade PnL
- [x] Unrealized PnL no longer treated as Daily PnL
- [x] WebSocket payload renamed to unrealizedPnl correctly
- [x] Trade History Exit Reason added
- [x] Trade History WHY / DIAGNOSTIC added
- [x] LIKELY_SL_HIT / LIKELY_TP_HIT logic added
- [x] LOSS_EXIT / PROFIT_EXIT logic added
- [x] exitReason / diagnosticReason frontend typing added
- [x] useTradesData allTrades integration added
- [x] Dashboard blank-screen crash fixed
- [x] Scanner M/S >= 60 filtering added
- [x] Scanner Top 10 qualified candidates added
- [x] Dynamic chart watchlist symbols added
- [x] Signals actionable view improved
- [x] Strategy Lab Open / Closed lifecycle added
- [x] Strategy Lab Win / Loss tracking added
- [x] Strategy Lab SL Hit / TP Hit tracking added
- [x] Strategy Lab Net PnL / Avg R added
- [x] Strategy Lab exit reason / diagnostic reason added
- [x] Strategy Lab persistence added
- [x] Frontend tests 19/19 passed
- [x] Frontend production build passed
- [x] Backend /health verified
- [x] Bybit Demo account data verified
- [x] Commit 252bae2 pushed
- [x] Commit 07e799e pushed

---

## Task 1 — Chart Symbol Search

- [x] Add manual symbol search
- [x] Search any valid Bybit USDT symbol
- [x] Search works even if symbol is not in Scanner Top 10
- [x] Existing scanner/watchlist quick-select remains
- [x] 1m / 5m / 15m works
- [x] Invalid symbol shows clean error
- [x] Frontend tests pass
- [x] Production build passes
- [x] UI verified
- [x] Commit + push
- [x] Mark Task 1 complete

---

## Task 2 — Today Trade Summary

- [x] Total trades today
- [x] Open trades
- [x] Closed trades
- [x] SL hits
- [x] TP hits
- [x] Wins
- [x] Losses
- [x] Realized PnL USDT
- [x] Win Rate
- [x] Gross Profit
- [x] Gross Loss
- [x] Average Win
- [x] Average Loss
- [x] Profit Factor
- [x] Best Trade
- [x] Worst Trade
- [x] Header Daily PnL and Today Summary use same source
- [x] Today / 7D / Custom still work
- [x] Tests/build/UI verify
- [x] Commit + push
- [x] Mark Task 2 complete

---

## Task 3 — SL Root-Cause Analysis

- [x] Persist entry-time diagnostic snapshot
- [x] 1H trend
- [x] 15M setup/trend
- [x] 5M entry context
- [x] RSI
- [x] ADX
- [x] ATR
- [x] Volume / RVOL
- [x] EMA alignment
- [x] Market structure
- [x] Entry/setup quality
- [x] SL distance vs ATR
- [x] COUNTER_TREND_ENTRY
- [x] LOW_ADX_RANGING_MARKET
- [x] LATE_ENTRY
- [x] OVEREXTENDED_RSI
- [x] LOW_VOLUME_CONFIRMATION
- [x] FAILED_BREAKOUT
- [x] STRUCTURE_REVERSAL
- [x] VOLATILITY_SPIKE
- [x] SL_TOO_TIGHT_FOR_ATR
- [x] POOR_RR_STRUCTURE
- [x] ENTRY_NEAR_SUPPORT
- [x] ENTRY_NEAR_RESISTANCE
- [x] MOMENTUM_REVERSAL
- [x] UNKNOWN_INSUFFICIENT_EVIDENCE
- [x] Show primary reason
- [x] Show secondary reasons
- [x] Show factual evidence
- [x] Aggregate SL reason statistics
- [x] Tests/build/UI verify
- [x] Commit + push
- [x] Mark Task 3 complete

---

## Task 4 — Visible AI Analysis

- [ ] Show AI enabled/disabled status
- [ ] Show provider/model
- [ ] Show last analysis time
- [ ] Show analyzed symbol
- [ ] Show market regime
- [ ] Show AI confidence
- [ ] Show factual context sent to AI
- [ ] Show AI output/advice
- [ ] ALLOW / CAUTION / BLOCK status
- [ ] AI analysis history
- [ ] Show API/runtime errors
- [ ] AI stays advisor/diagnostic layer
- [ ] Tests/build/UI verify
- [ ] Commit + push
- [ ] Mark Task 4 complete

---

## Task 5 — Strategy Lab $100 Paper Fund

- [ ] AMD starts with $100
- [ ] ICT starts with $100
- [ ] SMC starts with $100
- [ ] Liquidity Sweep starts with $100
- [ ] Starting balance
- [ ] Current equity
- [ ] Realized PnL
- [ ] Open PnL
- [ ] Return %
- [ ] Position size
- [ ] Risk amount
- [ ] Risk %
- [ ] Entry
- [ ] Paper SL
- [ ] Paper TP
- [ ] Exit
- [ ] PnL USDT
- [ ] PnL %
- [ ] R multiple
- [ ] Exit reason
- [ ] Diagnostic reason
- [ ] Balance updates after closed trade
- [ ] Open trades not counted as wins/losses
- [ ] No exchange order execution from Strategy Lab
- [ ] Tests/build/UI verify
- [ ] Commit + push
- [ ] Mark Task 5 complete

---

## Final Release Checks

- [ ] Backend tests pass
- [ ] Frontend tests pass
- [ ] Production build passes
- [ ] Backend health passes
- [ ] Bybit private API stability passes
- [ ] WebSocket verified
- [ ] Dashboard verified
- [ ] Scanner verified
- [ ] Signals verified
- [ ] Active Trade & History verified
- [ ] Performance verified
- [ ] Strategy Lab verified
- [ ] AI panel verified
- [ ] Git working tree reviewed
- [ ] Latest commit pushed to main
- [ ] Vercel production updated
- [ ] Production verified




