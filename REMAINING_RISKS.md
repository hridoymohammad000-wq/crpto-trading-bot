# Remaining Risks

## Intentional State Deferrals
- The pipeline intentionally defers some validation metrics to the final `Risk Engine` phase. While the State Machine securely prevents unauthorized symbols from executing, heavily volatile markers (like high slippage outside typical checks) are deferred into execution readiness rather than scanner rejection. This relies strictly on `app/readiness/` functionality.

## Network Failures
- Although the scanner universe refresh spam was resolved using an enforced backoff (attempt tracking), prolonged upstream API failures for Bybit Market Data might still stall dynamic symbol turnover updates. Symbols with missing updates safely transition down or remain locked in safe fallback states, but candidate lists can become stale if network disruptions persist beyond hours.

## External Restart Sequences
- Local persistence securely captures state; however, if the runtime bot is forcibly killed while interacting with SQLite during an active state write mapping operation, there remains a standard theoretical risk of partial snapshot tearing. Recovery hydration is defensive and forces unverified orders into `UNKNOWN_RECONCILING` to block subsequent execution until manual alignment is made.

## Strategy Limits
- The 15m/5m/1m timing pipeline is statically bound to chronological close timestamps. There exists a minimal window at exact boundary intersections (e.g. at the exact millisecond of a 5m close before Bybit has finalized data aggregation) where the candle tracking may pull a partially closed or empty candle result until the next cycle. No immediate hazard is presented because the system explicitly requires `is_closed == True` enforcement. 
