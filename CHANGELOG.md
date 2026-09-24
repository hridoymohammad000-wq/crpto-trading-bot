# Changelog

## Fixed
- **Runtime:** Resolved an issue where a failing scanner universe refresh would ignore wait bounds and cause continuous loop polling on external APIs (`app/bot/runtime.py`).
- **State Machine:** Corrected an issue where invalid 15m context evaluations inappropriately advanced states to `WATCHING` instead of rejecting them as `INVALIDATED` (`app/scanner/state_machine.py`).
- **Scanner Diagnostics:** Fixed missing `execution_status` in `/scanner/symbol/{symbol}` endpoint ensuring block reasons display properly in frontend UI (`app/api/routes/scanner.py`).
- **Execution Tracking:** Modified the state machine pipeline in `runtime.py` to correctly flag non-allowlisted symbols with `BLOCKED_BY_EXECUTION_ALLOWLIST` when a 5m signal triggers but fails authorization bounds.
- **Execution State:** Safely utilized `PipelineStateMachine.mark_executed` when handling order fulfillment rather than manually mutating the state object and ignoring diagnostics storage.

## Added
- **Tests:** Integrated new behavioral regression tests validating pipeline state transitions (`WATCHING` -> `ARMED` -> `TRIGGERED`), context evaluation paths, and exact diagnostic updates inside `test_scanner_runtime_behavior.py`.
