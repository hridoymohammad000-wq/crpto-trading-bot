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

- [ ] Persist entry-time diagnostic snapshot
- [ ] 1H trend
- [ ] 15M setup/trend
- [ ] 5M entry context
- [ ] RSI
- [ ] ADX
- [ ] ATR
- [ ] Volume / RVOL
- [ ] EMA alignment
- [ ] Market structure
- [ ] Entry/setup quality
- [ ] SL distance vs ATR
- [ ] COUNTER_TREND_ENTRY
- [ ] LOW_ADX_RANGING_MARKET
- [ ] LATE_ENTRY
- [ ] OVEREXTENDED_RSI
- [ ] LOW_VOLUME_CONFIRMATION
- [ ] FAILED_BREAKOUT
- [ ] STRUCTURE_REVERSAL
- [ ] VOLATILITY_SPIKE
- [ ] SL_TOO_TIGHT_FOR_ATR
- [ ] POOR_RR_STRUCTURE
- [ ] ENTRY_NEAR_SUPPORT
- [ ] ENTRY_NEAR_RESISTANCE
- [ ] MOMENTUM_REVERSAL
- [ ] UNKNOWN_INSUFFICIENT_EVIDENCE
- [ ] Show primary reason
- [ ] Show secondary reasons
- [ ] Show factual evidence
- [ ] Aggregate SL reason statistics
- [ ] Tests/build/UI verify
- [ ] Commit + push
- [ ] Mark Task 3 complete

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



