import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from app.bot.state import BotState, bot_state
from app.models.candle import SupportedSymbol
from app.strategies.service import StrategyService
from app.risk import RiskService
from app.execution import ExecutionService
from app.models.risk import RiskDecisionStatus
from app.repositories import ActivityRepository
from app.activity import ActivityService
from app.realtime.hub import RealtimeHub
from app.persistence import PersistenceDatabase
from app.readiness import TradingReadinessService
from app.models.readiness import TradingReadinessStatus
from app.bot.leadership import RuntimeLeadership, RuntimeLeadershipError

logger = logging.getLogger(__name__)

from app.scanner.engine import ScannerEngine

DEFAULT_SYMBOLS: tuple[SupportedSymbol, ...] = ("BTCUSDT",)


class BotRuntime:
    """Owns the single in-process market/strategy worker.

    Phase 4 is deliberately read-only: it evaluates the existing strategy and
    records runtime diagnostics, but never submits an order. Risk/execution are
    added in later phases.
    """

    def __init__(
        self,
        strategy_service: StrategyService,
        *,
        scanner_engine: ScannerEngine | None = None,
        risk_service: RiskService | None = None,
        execution_service: ExecutionService | None = None,
        activity_repository: ActivityRepository | None = None,
        activity_service: ActivityService | None = None,
        realtime_hub: RealtimeHub | None = None,
        persistence: PersistenceDatabase | None = None,
        reconciliation_engine: Any | None = None,
        trading_readiness_service: TradingReadinessService | None = None,
        runtime_leadership: RuntimeLeadership | None = None,
        state: BotState = bot_state,
        symbols: Sequence[SupportedSymbol] = DEFAULT_SYMBOLS,
        poll_interval_seconds: float = 15.0,
        trade_sync_interval_seconds: float = 60.0,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than zero")
        if trade_sync_interval_seconds <= 0:
            raise ValueError("trade_sync_interval_seconds must be greater than zero")
        self._strategy_service = strategy_service
        self._scanner_engine = scanner_engine
        self._risk_service = risk_service
        self._execution_service = execution_service
        self._activity_repository = activity_repository
        self._activity_service = activity_service
        self._realtime_hub = realtime_hub
        self._persistence = persistence
        self._reconciliation_engine = reconciliation_engine
        self._trading_readiness_service = trading_readiness_service
        self._runtime_leadership = runtime_leadership
        self._state = state
        self._symbols = tuple(symbols)
        self._poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._started_at: datetime | None = None
        self._last_heartbeat: datetime | None = None
        self._last_cycle_at: datetime | None = None
        self._cycle_count = 0
        self._latest_results: dict[str, dict[str, Any]] = {}
        self._last_error: str | None = None
        self._submitted_signal_ids: set[str] = set()
        self._startup_reconciliation_complete = reconciliation_engine is None
        self._trade_sync_interval_seconds = trade_sync_interval_seconds
        self._last_trade_sync_attempt_at: datetime | None = None
        self._last_trade_sync_success_at: datetime | None = None
        self._cycle_in_progress: bool = False
        self._current_cycle_stage: str | None = None
        self._last_cycle_start_time: datetime | None = None
        self._last_completed_cycle_time: datetime | None = None
        self._last_cycle_duration_seconds: float | None = None
        self._last_blocking_stage: str | None = None

    @property
    def worker_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        async with self._lock:
            if self.worker_running:
                self._state.start()
                return
            if self._runtime_leadership is not None and not self._runtime_leadership.acquire():
                metadata = self._runtime_leadership.owner_metadata() or {}
                owner_pid = metadata.get("pid")
                self._last_error = (
                    "Trading runtime leadership is already owned"
                    + (f" by PID {owner_pid}" if owner_pid is not None else " by another process")
                )
                self._state.stop()
                raise RuntimeLeadershipError(self._last_error)
            self._stop_event = asyncio.Event()
            now = datetime.now(timezone.utc)
            self._started_at = now
            self._last_heartbeat = now
            self._last_cycle_at = None
            self._cycle_count = 0
            self._latest_results = {}
            self._last_error = None
            self._last_trade_sync_attempt_at = None
            self._last_trade_sync_success_at = None
            # Resolve any durable order intent left non-terminal by a previous
            # process before normal startup reconciliation. Recovery is lookup-
            # only and never blindly re-submits an order.
            if self._execution_service is not None:
                recover = getattr(self._execution_service, "recover_unresolved", None)
                if callable(recover):
                    try:
                        await recover()
                    except Exception as exc:
                        self._last_error = (
                            f"Execution recovery failed: {type(exc).__name__}: {exc}"
                        )

            self._submitted_signal_ids = (
                self._persistence.submitted_signal_ids()
                if self._persistence is not None
                else self._activity_repository.submitted_signal_ids()
                if self._activity_repository is not None
                else set()
            )

            # Fail closed on restart: local durable state is hydrated first, then
            # exchange/account/order/position state is reconciled synchronously
            # before the worker can evaluate an entry. The worker may still run
            # for observation after a failed reconciliation, but readiness will
            # block all new exposure until a later reconciliation succeeds.
            self._startup_reconciliation_complete = self._reconciliation_engine is None
            if self._reconciliation_engine is not None:
                try:
                    await self._reconciliation_engine.reconcile()
                except Exception as exc:
                    self._last_error = f"Startup reconciliation failed: {type(exc).__name__}: {exc}"
                finally:
                    self._startup_reconciliation_complete = bool(
                        getattr(self._reconciliation_engine, "has_completed_once", False)
                    )

            self._state.start()
            if self._persistence is not None:
                self._persistence.set_metadata("last_requested_bot_status", "RUNNING")
            self._task = asyncio.create_task(self._run(), name="trading-bot-runtime")
            await self._publish("bot_status", {"status": "RUNNING", "isAutomatedExecutionEnabled": self._execution_service is not None})

    async def stop(self) -> None:
        async with self._lock:
            task = self._task
            self._stop_event.set()
            self._state.stop()
            if self._persistence is not None:
                self._persistence.set_metadata("last_requested_bot_status", "STOPPED")
            await self._publish("bot_status", {"status": "STOPPED", "isAutomatedExecutionEnabled": self._execution_service is not None})
            if task is None:
                if self._runtime_leadership is not None:
                    self._runtime_leadership.release()
                return
            if task is asyncio.current_task():
                return

        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            async with self._lock:
                if self._task is task:
                    self._task = None
                if self._runtime_leadership is not None:
                    self._runtime_leadership.release()

    async def shutdown(self) -> None:
        await self.stop()

    def snapshot(self) -> dict[str, Any]:
        return {
            "bot_status": self._state.status.value,
            "worker_running": self.worker_running,
            "started_at": self._iso(self._started_at),
            "last_heartbeat": self._iso(self._last_heartbeat),
            "last_cycle_at": self._iso(self._last_cycle_at),
            "cycle_in_progress": self._cycle_in_progress,
            "current_cycle_stage": self._current_cycle_stage,
            "last_cycle_start_time": self._iso(self._last_cycle_start_time),
            "last_completed_cycle_time": self._iso(self._last_completed_cycle_time),
            "last_cycle_duration_seconds": self._last_cycle_duration_seconds,
            "last_blocking_stage": self._last_blocking_stage,
            "cycle_count": self._cycle_count,
            "poll_interval_seconds": self._poll_interval_seconds,
            "symbols": list(self._symbols),
            "latest_results": self._latest_results,
            "last_error": self._last_error,
            "risk_enabled": self._risk_service is not None,
            "execution_enabled": self._execution_service is not None,
            "trading_readiness": (
                self._trading_readiness_service.last_decision.model_dump(mode="json")
                if self._trading_readiness_service is not None
                and self._trading_readiness_service.last_decision is not None
                else None
            ),
            "submitted_signal_count": len(self._submitted_signal_ids),
            "startup_reconciliation_complete": self._startup_reconciliation_complete,
            "runtime_leadership": {
                "enabled": self._runtime_leadership is not None,
                "is_owner": (
                    self._runtime_leadership.is_owner
                    if self._runtime_leadership is not None
                    else True
                ),
                "owner_pid": (
                    self._runtime_leadership.owner_pid
                    if self._runtime_leadership is not None
                    else None
                ),
            },
            "restart_recovery": {
                "persistent": self._persistence is not None,
                "recovered_submitted_signal_ids": len(self._submitted_signal_ids),
                "auto_restart_enabled": False,
                "safety_note": "Bot remains stopped after process restart until explicitly started.",
            },
        }

    async def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                self._last_heartbeat = datetime.now(timezone.utc)
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self._poll_interval_seconds
                    )
                    break
                except TimeoutError:
                    pass

                if self._stop_event.is_set():
                    break
                await self._run_cycle()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # defensive worker boundary
            self._last_error = f"{type(exc).__name__}: {exc}"
            self._state.stop()
            logger.exception("Bot runtime worker stopped unexpectedly")
        finally:
            self._last_heartbeat = datetime.now(timezone.utc)

    async def _run_cycle(self) -> None:
        from app.scanner.models import SetupState, SymbolState
        from app.scanner.state_machine import PipelineStateMachine
        from app.core.config import settings

        self._cycle_in_progress = True
        self._last_cycle_start_time = datetime.now(timezone.utc)
        cycle_time = self._last_cycle_start_time
        results: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        async def _timed_await(stage_name: str, awaitable: Any, timeout: float = 30.0) -> Any:
            self._current_cycle_stage = stage_name
            self._last_blocking_stage = stage_name
            t0 = datetime.now(timezone.utc)
            try:
                res = await asyncio.wait_for(awaitable, timeout=timeout)
                t1 = datetime.now(timezone.utc)
                logger.debug("Stage %s completed in %.3fs", stage_name, (t1 - t0).total_seconds())
                self._last_blocking_stage = None
                return res
            except asyncio.TimeoutError:
                logger.error("Stage %s timed out after %.1fs", stage_name, timeout)
                raise

        # Sync recent closed Bybit Demo trades into SQLite on a controlled
        # cadence. Record the ATTEMPT time before awaiting so an outage does
        # not retry on every normal bot cycle. Sync failure is non-fatal.
        if self._activity_service is not None:
            sync_due = (
                self._last_trade_sync_attempt_at is None
                or (cycle_time - self._last_trade_sync_attempt_at).total_seconds()
                >= self._trade_sync_interval_seconds
            )
            if sync_due:
                self._last_trade_sync_attempt_at = cycle_time
                try:
                    synced = await _timed_await("sync_closed_trades", self._activity_service.sync_closed_trades(), 15.0)
                    self._last_trade_sync_success_at = cycle_time
                    logger.info(
                        "Closed trade sync completed: %d recent trades upserted",
                        synced,
                    )
                except Exception as exc:
                    logger.warning(
                        "Closed trade sync failed (non-fatal): %s: %s",
                        type(exc).__name__,
                        exc,
                    )

        # Refresh scanner universe on first cycle, then every 15 minutes.
        if self._scanner_engine:
            try:
                last_refresh = getattr(
                    self._scanner_engine,
                    "_last_universe_refresh",
                    None,
                )
                last_attempt = getattr(self, "_last_universe_refresh_attempt", None)

                refresh_due = (
                    last_refresh is None
                    or (cycle_time - last_refresh).total_seconds() >= 900
                )
                
                if refresh_due and last_attempt is not None and (cycle_time - last_attempt).total_seconds() < 900:
                    refresh_due = False

                if refresh_due:
                    self._last_universe_refresh_attempt = cycle_time
                    await _timed_await("refresh_universe", self._scanner_engine.refresh_universe(), 150.0)

            except Exception as exc:
                logger.warning(
                    "Scanner universe refresh failed: %s",
                    exc,
                )

        if self._scanner_engine and self._execution_service:
            try:
                positions = await _timed_await("get_positions", self._execution_service.get_positions(), 15.0)
                self._scanner_engine.watchlist.open_position_symbols = {p.symbol for p in positions if p.size > 0}
            except Exception as exc:
                logger.warning("Failed to fetch positions during cycle (non-fatal): %s: %s", type(exc).__name__, exc)
                
        if self._reconciliation_engine:
            try:
                await _timed_await("reconcile", self._reconciliation_engine.reconcile(), 15.0)
                self._startup_reconciliation_complete = bool(
                    getattr(self._reconciliation_engine, "has_completed_once", False)
                )
            except Exception as exc:
                self._startup_reconciliation_complete = False
                logger.warning("Runtime reconciliation failed: %s", exc)
            
        symbols = (
            sorted(self._scanner_engine.watchlist.all_monitored)
            if self._scanner_engine
            else self._symbols
        )
        allowlist = settings.execution_symbol_allowlist
        
        for symbol in symbols:
            if self._stop_event.is_set():
                break
            try:
                # If scanner engine exists, use state machine pipeline
                if self._scanner_engine:
                    # ScannerEngine owns execution-selection semantics. Always obtain
                    # state through it so STATIC vs SCANNER permissions stay authoritative.
                    state = self._scanner_engine.get_or_create_state(symbol)
                        
                    # Refresh permission after cooldown/state transitions without
                    # overwriting ScannerEngine's SCANNER-mode decision with the
                    # global static allowlist.
                    state.execution_allowed = self._scanner_engine._is_execution_allowed(symbol)
                    
                    # Clear lockout if reconciliation engine is now safe
                    if self._reconciliation_engine and self._reconciliation_engine.is_safe():
                        if state.execution_diagnostics.get("execution_status") == "UNKNOWN_RECONCILING":
                            state.execution_diagnostics.pop("execution_status", None)
                            if "RECONCILIATION_MISMATCH" in state.reason_codes:
                                state.reason_codes = ["RECOVERED"]
                    
                    if state.execution_diagnostics.get("execution_status") == "UNKNOWN_RECONCILING":
                        state.execution_allowed = False
                        state.reason_codes = ["RECONCILIATION_MISMATCH"]
                    
                    # Fetch candles for tracking
                    raw_15m = await _timed_await(f"fetch_15m_{symbol}", self._strategy_service._market_data.fetch_candles(symbol, "15m", limit=30, closed_only=True), 10.0)
                    raw_5m = await _timed_await(f"fetch_5m_{symbol}", self._strategy_service._market_data.fetch_candles(symbol, "5m", limit=200, closed_only=True), 10.0)
                    raw_1m = await _timed_await(f"fetch_1m_{symbol}", self._strategy_service._market_data.fetch_candles(symbol, "1m", limit=2, closed_only=True), 10.0)
                    c_15m = tuple(candle for candle in raw_15m if candle.is_closed)
                    c_5m = tuple(candle for candle in raw_5m if candle.is_closed)
                    c_1m = tuple(candle for candle in raw_1m if candle.is_closed)
                    
                    # Check new candles
                    new_15m = bool(c_15m) and (state.last_processed_15m != c_15m[-1].start_time)
                    new_5m = bool(c_5m) and (state.last_processed_5m != c_5m[-1].start_time)
                    new_1m = bool(c_1m) and (state.last_processed_1m != c_1m[-1].start_time)
                    
                    # State Machine Pipeline
                    if state.state != SetupState.COOLDOWN:
                        if c_15m and (new_15m or state.state == SetupState.DISCOVERED):
                            PipelineStateMachine.evaluate_15m_context(state, c_15m)
                            
                        # Strategy authority is 5m. Evaluate exactly once per newly
                        # closed 5m candle; a new 15m context alone must not trigger
                        # an entry evaluation. TRIGGERED is re-evaluated on a later
                        # 5m close so stale setups can be refreshed/invalidated.
                        if c_5m and state.state in (SetupState.WATCHING, SetupState.ARMED, SetupState.TRIGGERED) and new_5m:
                            evaluation = await _timed_await(f"evaluate_{symbol}", self._strategy_service.evaluate(symbol), 15.0)
                            PipelineStateMachine.evaluate_5m_setup(state, evaluation)
                            if state.state == SetupState.ARMED:
                                if state.execution_allowed:
                                    PipelineStateMachine.arm_strategy_authority_trigger(state)
                                else:
                                    state.execution_diagnostics["execution_status"] = "BLOCKED_BY_EXECUTION_ALLOWLIST"
                        
                    is_triggered = state.state == SetupState.TRIGGERED
                    signal = state.trigger_1m.get("signal")
                    execution_allowed = state.execution_allowed
                else:
                    # Fallback for old tests without scanner engine
                    evaluation = await _timed_await(f"evaluate_{symbol}", self._strategy_service.evaluate(symbol), 15.0)
                    is_triggered = evaluation.signal is not None
                    signal = evaluation.signal
                    execution_allowed = symbol in allowlist
                    
                risk_decision = None
                execution_result = None
                
                if is_triggered:
                    if self._scanner_engine is None:
                        signal = evaluation.signal
                    else:
                        signal = state.trigger_1m.get("signal")
                        
                    if signal and self._risk_service is not None:
                        risk_decision = await _timed_await(f"risk_{symbol}", self._risk_service.evaluate(signal), 10.0)
                        if risk_decision.status == RiskDecisionStatus.READY:
                            if execution_allowed:
                                readiness_decision = None
                                if self._trading_readiness_service is not None:
                                    readiness_decision = await _timed_await(f"readiness_{symbol}", self._trading_readiness_service.evaluate(
                                        signal,
                                        risk_decision,
                                        execution_allowed=execution_allowed,
                                        cooldown_active=(
                                            self._scanner_engine is not None
                                            and state.state == SetupState.COOLDOWN
                                        ),
                                        duplicate_signal=(
                                            signal.signal_id in self._submitted_signal_ids
                                        ),
                                        startup_reconciliation_complete=(
                                            self._startup_reconciliation_complete
                                        ),
                                    ), 10.0)
                                    if readiness_decision.status is not TradingReadinessStatus.READY:
                                        if self._scanner_engine:
                                            state.state = SetupState.INVALIDATED
                                            state.reason_codes = [
                                                reason.value
                                                for reason in readiness_decision.reason_codes
                                            ]
                                            state.execution_diagnostics["execution_status"] = "BLOCKED_BY_TRADING_READINESS"
                                            state.execution_diagnostics["readiness_reasons"] = state.reason_codes
                                elif self._reconciliation_engine and not self._reconciliation_engine.is_safe():
                                    if self._scanner_engine:
                                        state.state = SetupState.INVALIDATED
                                        state.reason_codes = ["RECONCILIATION_MISMATCH"]

                                readiness_allows_execution = (
                                    readiness_decision is None
                                    or readiness_decision.status is TradingReadinessStatus.READY
                                )
                                if (
                                    readiness_allows_execution
                                    and self._execution_service is not None
                                    and signal.signal_id not in self._submitted_signal_ids
                                ):
                                    execution_result = await _timed_await(f"execute_{symbol}", self._execution_service.execute(risk_decision), 20.0)
                                    if execution_result.status.value in {
                                        "SUBMITTED",
                                        "ACKNOWLEDGED",
                                        "PARTIALLY_FILLED",
                                        "FILLED",
                                    }:
                                        self._submitted_signal_ids.add(signal.signal_id)
                                        if self._scanner_engine:
                                            PipelineStateMachine.mark_executed(state, execution_result.order_id)
                                            self._scanner_engine.enter_cooldown(symbol)
                                            state.execution_diagnostics["execution_status"] = execution_result.status.value
                                    elif execution_result.status.value == "UNKNOWN_RECONCILING":
                                        self._submitted_signal_ids.add(signal.signal_id)
                                        if self._scanner_engine:
                                            PipelineStateMachine.invalidate(state, "ORDER_OUTCOME_UNKNOWN")
                                            state.execution_diagnostics["execution_status"] = "UNKNOWN_RECONCILING"
                                    else:
                                        if self._scanner_engine:
                                            state.state = SetupState.INVALIDATED
                                            state.reason_codes = ["ORDER_FAILED"]
                            else:
                                if self._scanner_engine:
                                    state.state = SetupState.INVALIDATED
                                    state.reason_codes = ["BLOCKED_BY_EXECUTION_ALLOWLIST"]
                                    state.execution_diagnostics["execution_status"] = "BLOCKED_BY_EXECUTION_ALLOWLIST"
                        else:
                            if self._scanner_engine:
                                state.state = SetupState.INVALIDATED
                                state.reason_codes = ["RISK_REJECTED"]
                            
                    if signal and self._activity_repository is not None:
                        self._activity_repository.record_signal(
                            signal,
                            risk=risk_decision,
                            execution=execution_result,
                        )
                    
                    if signal:
                        signal_status = "Executed" if execution_result and execution_result.status.value in {"SUBMITTED", "ACKNOWLEDGED", "PARTIALLY_FILLED", "FILLED"} else ("Blocked" if not execution_allowed else "Rejected" if risk_decision else "New")
                        await _timed_await("publish_signal", self._publish(
                            "signal_generated",
                            {
                                "signal": {
                                    "id": signal.signal_id,
                                    "symbol": signal.symbol,
                                    "strategy": signal.strategy,
                                    "side": signal.side.value,
                                    "timeframe": signal.entry_timeframe,
                                    "entry": float(signal.reference_entry_price),
                                    "sl": float(risk_decision.stop_loss) if risk_decision and risk_decision.stop_loss else 0.0,
                                    "tp": float(risk_decision.take_profit) if risk_decision and risk_decision.take_profit else 0.0,
                                    "confidence": signal.confidence,
                                    "timestamp": signal.signal_time.isoformat(),
                                    "age": "now",
                                    "status": signal_status,
                                }
                            },
                        ), 5.0)
                        if execution_result:
                            await _timed_await("publish_event", self._publish(
                                "system_event",
                                {
                                    "level": "success" if execution_result.status.value in {"SUBMITTED", "ACKNOWLEDGED", "PARTIALLY_FILLED", "FILLED"} else "error",
                                    "message": f"{signal.symbol} execution {execution_result.status.value.lower()}",
                                    "details": execution_result.model_dump(mode="json"),
                                },
                            ), 5.0)
                            
                if self._scanner_engine:
                    results[symbol] = {
                        "state": state.state.value,
                        "reason_codes": state.reason_codes,
                        "execution_allowed": state.execution_allowed
                    }
                else:
                    results[symbol] = {
                        "evaluation_time": evaluation.evaluation_time.isoformat(),
                        "signal": (evaluation.signal.model_dump(mode="json") if evaluation.signal else None),
                        "risk_decision": (risk_decision.model_dump(mode="json") if risk_decision else None),
                        "execution": (execution_result.model_dump(mode="json") if execution_result else None),
                        "reason_codes": [r.value for r in evaluation.reason_codes],
                    }
            except Exception as exc:  # isolate one symbol from the rest
                message = f"{symbol}: {type(exc).__name__}: {exc}"
                errors.append(message)
                results[symbol] = {"error": message}
                logger.exception("Strategy evaluation failed for %s", symbol)
                await self._publish("system_event", {"level": "error", "message": f"{symbol} strategy evaluation failed", "details": message})

        self._latest_results = results
        self._last_completed_cycle_time = datetime.now(timezone.utc)
        self._last_cycle_duration_seconds = (self._last_completed_cycle_time - self._last_cycle_start_time).total_seconds()
        self._last_cycle_at = self._last_completed_cycle_time
        self._last_heartbeat = self._last_completed_cycle_time
        self._cycle_count += 1
        self._last_error = "; ".join(errors) if errors else None
        self._cycle_in_progress = False
        self._current_cycle_stage = None


    async def _publish(self, event: str, data: Any) -> None:
        if self._realtime_hub is not None:
            await self._realtime_hub.publish(event, data)

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None
