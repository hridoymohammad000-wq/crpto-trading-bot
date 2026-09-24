import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.bot.runtime import BotRuntime
from app.bot.state import BotState, BotStatus


class FakeStrategyService:
    def __init__(self, failing_symbol: str | None = None) -> None:
        self.calls: list[str] = []
        self.failing_symbol = failing_symbol

    async def evaluate(self, symbol: str):
        self.calls.append(symbol)
        if symbol == self.failing_symbol:
            raise RuntimeError("simulated strategy failure")
        return SimpleNamespace(
            evaluation_time=datetime.now(timezone.utc),
            signal=None,
            reason_codes=(),
        )


def test_runtime_start_runs_cycles_and_stop_is_clean() -> None:
    async def scenario() -> None:
        service = FakeStrategyService()
        state = BotState()
        runtime = BotRuntime(
            service, state=state, symbols=("BTCUSDT",), poll_interval_seconds=0.01
        )

        await runtime.start()
        await asyncio.sleep(0.035)
        snapshot = runtime.snapshot()

        assert state.status == BotStatus.RUNNING
        assert snapshot["worker_running"] is True
        assert snapshot["cycle_count"] >= 1
        assert service.calls
        assert snapshot["execution_enabled"] is False

        await runtime.stop()
        assert state.status == BotStatus.STOPPED
        assert runtime.snapshot()["worker_running"] is False

    asyncio.run(scenario())


def test_runtime_start_is_idempotent_no_duplicate_worker() -> None:
    async def scenario() -> None:
        service = FakeStrategyService()
        runtime = BotRuntime(
            service,
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=0.05,
        )
        await runtime.start()
        first_task = runtime._task
        await runtime.start()
        second_task = runtime._task

        assert first_task is second_task
        await runtime.stop()

    asyncio.run(scenario())


def test_runtime_isolates_symbol_error_and_keeps_worker_alive() -> None:
    async def scenario() -> None:
        service = FakeStrategyService(failing_symbol="ETHUSDT")
        runtime = BotRuntime(
            service,
            state=BotState(),
            symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT"),
            poll_interval_seconds=0.01,
        )
        await runtime.start()
        await asyncio.sleep(0.025)
        snapshot = runtime.snapshot()

        assert snapshot["worker_running"] is True
        assert snapshot["cycle_count"] >= 1
        assert "ETHUSDT" in snapshot["latest_results"]
        assert "error" in snapshot["latest_results"]["ETHUSDT"]
        assert "BTCUSDT" in service.calls
        assert "SOLUSDT" in service.calls
        await runtime.stop()

    asyncio.run(scenario())


def test_runtime_stop_is_idempotent() -> None:
    async def scenario() -> None:
        runtime = BotRuntime(
            FakeStrategyService(),
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=0.05,
        )
        await runtime.stop()
        await runtime.stop()
        assert runtime.snapshot()["bot_status"] == "stopped"

    asyncio.run(scenario())


def test_runtime_performs_startup_reconciliation_before_worker_starts() -> None:
    class FakeReconciliation:
        def __init__(self) -> None:
            self.calls = 0
            self.has_completed_once = False

        async def reconcile(self) -> None:
            self.calls += 1
            self.has_completed_once = True

    async def scenario() -> None:
        reconciliation = FakeReconciliation()
        runtime = BotRuntime(
            FakeStrategyService(),
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=0.05,
            reconciliation_engine=reconciliation,
        )

        await runtime.start()
        assert reconciliation.calls == 1
        assert runtime.snapshot()["startup_reconciliation_complete"] is True
        assert runtime.worker_running is True
        await runtime.stop()

    asyncio.run(scenario())


def test_runtime_recovers_local_submitted_ids_before_startup_reconciliation() -> None:
    from unittest.mock import Mock

    class CheckingReconciliation:
        def __init__(self, runtime_holder: dict[str, BotRuntime]) -> None:
            self.runtime_holder = runtime_holder
            self.has_completed_once = False
            self.saw_recovered_id = False

        async def reconcile(self) -> None:
            runtime = self.runtime_holder["runtime"]
            self.saw_recovered_id = "persisted-signal" in runtime._submitted_signal_ids
            self.has_completed_once = True

    async def scenario() -> None:
        persistence = Mock()
        persistence.submitted_signal_ids.return_value = {"persisted-signal"}
        holder: dict[str, BotRuntime] = {}
        reconciliation = CheckingReconciliation(holder)
        runtime = BotRuntime(
            FakeStrategyService(),
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=0.05,
            persistence=persistence,
            reconciliation_engine=reconciliation,
        )
        holder["runtime"] = runtime

        await runtime.start()
        assert reconciliation.saw_recovered_id is True
        assert runtime.snapshot()["submitted_signal_count"] == 1
        await runtime.stop()

    asyncio.run(scenario())


def test_runtime_trade_sync_attempt_cadence_includes_failures() -> None:
    from datetime import timedelta

    class FailingActivityService:
        def __init__(self) -> None:
            self.calls = 0

        async def sync_closed_trades(self, *, limit: int = 100) -> int:
            self.calls += 1
            raise RuntimeError("simulated sync outage")

    async def scenario() -> None:
        activity = FailingActivityService()
        runtime = BotRuntime(
            FakeStrategyService(),
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=1.0,
            trade_sync_interval_seconds=60.0,
            activity_service=activity,  # type: ignore[arg-type]
        )

        await runtime._run_cycle()
        assert activity.calls == 1
        assert runtime._last_trade_sync_attempt_at is not None
        assert runtime._last_trade_sync_success_at is None

        # Failure must not cause a retry on the next normal strategy cycle.
        await runtime._run_cycle()
        assert activity.calls == 1

        # Once the attempt interval has elapsed, another attempt is allowed.
        runtime._last_trade_sync_attempt_at = (
            datetime.now(timezone.utc) - timedelta(seconds=61)
        )
        await runtime._run_cycle()
        assert activity.calls == 2

    asyncio.run(scenario())


def test_runtime_trade_sync_success_respects_interval() -> None:
    class ActivityServiceStub:
        def __init__(self) -> None:
            self.calls = 0

        async def sync_closed_trades(self, *, limit: int = 100) -> int:
            self.calls += 1
            return 3

    async def scenario() -> None:
        activity = ActivityServiceStub()
        runtime = BotRuntime(
            FakeStrategyService(),
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=1.0,
            trade_sync_interval_seconds=60.0,
            activity_service=activity,  # type: ignore[arg-type]
        )

        await runtime._run_cycle()
        await runtime._run_cycle()

        assert activity.calls == 1
        assert runtime._last_trade_sync_attempt_at is not None
        assert runtime._last_trade_sync_success_at is not None

    asyncio.run(scenario())
