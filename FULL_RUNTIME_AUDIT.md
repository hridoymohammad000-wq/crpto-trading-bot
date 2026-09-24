# Full Runtime Audit Report

## 1. Runtime Lifecycle
The bot runtime is managed centrally in `app.bot.runtime._run_cycle`. It utilizes a fail-closed execution boundary. Task crashes halt the automated strategy evaluation while safely preserving state. The system successfully separates leadership evaluation, readiness checks, and risk calculation.

## 2. Scanner Pipeline
The universe updates continuously (every 15m), and objects transition through:
`DISCOVERED` -> `WATCHING` -> `ARMED` -> `TRIGGERED` -> `EXECUTED` -> `COOLDOWN` -> `DISCOVERED`
Execution selection authority separates candidates statically (via allowlist) and dynamically.

## 3. Candle Pipeline
15m, 5m, and 1m tracking timestamps prevent stale evaluations. Strategy authority operates explicitly on 5m logic. The 1m trigger operates successfully without blocking core execution but acts as a diagnostic boundary for unauthorized execution attempts.

## 4. Signal Lifecycle
Signal duplicate suppression utilizes a durable memory `submitted_signal_ids` which persists and hydrates correctly. Transient failures before submission do not pollute the durable ID lock, allowing safe retries. No race conditions were detected in the signal lifecycle logic.

## 5. State Machine
All states are reachable. One conflicting state transition authority existed where `SetupState.EXECUTED` was skipped in favor of a direct mutation to `COOLDOWN`. This was corrected by properly invoking `PipelineStateMachine.mark_executed` and then triggering cooldown properly. An invalid fallback mechanism was also fixed where broken contexts mistakenly advanced to `WATCHING`.

## 6. API & Consistency
The scanner engine perfectly coordinates memory references with the API routes. A previous issue omitting the non-allowlist block reasons was fixed to accurately project internal execution diagnostics to the frontend API.

## 7. Frontend Integration & Persistence
Frontend appropriately processes the scanner responses and handles backend signals smoothly. Both runtime lock and state persistence hydrate safely without permanent stalls, honoring fail-closed operations. SQLite database usage is appropriately bound to the application lifespan.
