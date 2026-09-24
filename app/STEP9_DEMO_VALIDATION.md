# STEP 9 — Demo Auto-Execution Validation

This stage intentionally does **not** manufacture a trading signal or bypass Strategy/Risk/TradingReadiness.

## 1. Local prerequisites

Use Bybit **Demo** credentials in `backend/.env` (never commit them), and enable execution only for the controlled Demo run:

```env
BYBIT_DEMO=true
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
EXECUTION_ENABLED=true
```

Keep the normal scanner/strategy/risk settings unchanged.

## 2. Start backend

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

## 3. Start the bot through the authenticated control API/UI

Do not run multiple Uvicorn workers. The runtime leadership guard must show this process as owner.

## 4. Run the preflight

In another terminal from `backend`:

```powershell
.\.venv\Scripts\python.exe step9_preflight.py
```

Preflight must confirm Demo environment, UNIFIED account, margin mode, known available margin, SYNCED reconciliation, execution enabled, runtime leadership, startup reconciliation, and endpoint health.

## 5. Genuine signal validation

Do not inject a fake signal. Wait for the existing approved strategy to create a genuine fresh signal. For the first accepted Demo entry verify:

- State reaches `TRIGGERED` through existing strategy authority.
- RiskDecision is `READY`.
- TradingReadiness is `READY` with no blocking reason codes.
- A durable execution intent exists before the exchange POST.
- Bybit returns an order acknowledgement; HTTP acknowledgement is not treated as a fill.
- The exchange position/order appears through the normal account/reconciliation path.
- The actual exchange-side stop loss matches the durable execution intent.
- TP mismatch, if any, is surfaced as a warning according to current policy.
- Reconciliation returns `SYNCED` after protection is established.
- Restart/retry of the same signal does not create a second order.

Step 9 is complete only after that real Demo round-trip succeeds.
