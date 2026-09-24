import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.bot.leadership import RuntimeLeadership, RuntimeLeadershipError
from app.bot.runtime import BotRuntime
from app.bot.state import BotState
from app.models.readiness import TradingReadinessReason, TradingReadinessStatus
from tests.test_trading_readiness import build_service, evaluate


class FakeStrategyService:
    async def evaluate(self, symbol: str):
        return SimpleNamespace(
            evaluation_time=datetime.now(timezone.utc),
            signal=None,
            reason_codes=(),
        )


def test_only_one_leadership_owner_per_lock_file(tmp_path: Path) -> None:
    lock_path = tmp_path / "runtime.lock"
    first = RuntimeLeadership(lock_path)
    second = RuntimeLeadership(lock_path)

    assert first.acquire() is True
    assert first.is_owner is True
    assert second.acquire() is False
    assert second.is_owner is False

    first.release()
    assert second.acquire() is True
    assert second.is_owner is True
    second.release()


def test_second_runtime_cannot_start_while_leader_is_running(tmp_path: Path) -> None:
    async def scenario() -> None:
        lock_path = tmp_path / "runtime.lock"
        first_leadership = RuntimeLeadership(lock_path)
        second_leadership = RuntimeLeadership(lock_path)
        first = BotRuntime(
            FakeStrategyService(),
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=0.05,
            runtime_leadership=first_leadership,
        )
        second = BotRuntime(
            FakeStrategyService(),
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=0.05,
            runtime_leadership=second_leadership,
        )

        await first.start()
        assert first.worker_running is True
        assert first.snapshot()["runtime_leadership"]["is_owner"] is True

        with pytest.raises(RuntimeLeadershipError):
            await second.start()
        assert second.worker_running is False
        assert second.snapshot()["runtime_leadership"]["is_owner"] is False

        await first.stop()
        await second.start()
        assert second.worker_running is True
        assert second.snapshot()["runtime_leadership"]["is_owner"] is True
        await second.stop()

    asyncio.run(scenario())


def test_readiness_blocks_new_entry_when_runtime_is_not_leader(tmp_path: Path) -> None:
    leadership = RuntimeLeadership(tmp_path / "runtime.lock")
    service = build_service()
    service._runtime_leadership = leadership

    decision = evaluate(service)
    assert decision.status is TradingReadinessStatus.BLOCKED
    assert TradingReadinessReason.BLOCKED_DUPLICATE_RUNTIME in decision.reason_codes


def test_reduce_only_not_blocked_by_runtime_leadership(tmp_path: Path) -> None:
    leadership = RuntimeLeadership(tmp_path / "runtime.lock")
    service = build_service()
    service._runtime_leadership = leadership

    decision = evaluate(service, reduce_only=True)
    assert TradingReadinessReason.BLOCKED_DUPLICATE_RUNTIME not in decision.reason_codes
