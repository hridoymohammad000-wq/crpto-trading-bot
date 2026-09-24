# Root Cause Report

## 1. Scanner Refresh Spam on Failure
**Root Cause:**
In `app/bot/runtime.py`, the `_last_universe_refresh` timestamp was updated strictly inside the scanner engine *after* a successful network completion. When a network error occurred, the check `(cycle_time - last_refresh) >= 900` remained True indefinitely, causing the bot to bypass its schedule and bombard the exchange endpoint repeatedly every second.

**Resolution:**
Implemented an explicit `_last_universe_refresh_attempt` timestamp inside the bot runtime loop to ensure that even upon failure, the schedule backs off properly according to the configured wait bounds.

## 2. Unexposed API Execution Gating
**Root Cause:**
In `app/api/routes/scanner.py`, the `execution_status` property was hardcoded to `None` in the endpoint payload. The scanner state machine correctly calculated the status but the API willfully obscured it.

**Resolution:**
Exposed `state.execution_diagnostics.get("execution_status")` ensuring full parity between backend operations and frontend monitoring.

## 3. Masked Diagnostic Rejections
**Root Cause:**
In `app/bot/runtime.py`, if a symbol triggered but was not in the execution allowlist, the runtime refused to evaluate it but never properly marked `state.execution_diagnostics`. The symbol would stay `ARMED` while hiding the exact block reason from the API.

**Resolution:**
Updated the evaluation chain so `BLOCKED_BY_EXECUTION_ALLOWLIST` is accurately populated when execution permission fails for a valid setup.

## 4. State Machine Invalid Context Progression
**Root Cause:**
In `PipelineStateMachine.evaluate_15m_context`, a bug forced invalid HTF contexts transitioning out of `DISCOVERED` to advance into `WATCHING` instead of dropping to `INVALIDATED`. 

**Resolution:**
Corrected the conditional statement to preserve `DISCOVERED` or regress to `INVALIDATED` immediately, maintaining strict logical boundaries.
