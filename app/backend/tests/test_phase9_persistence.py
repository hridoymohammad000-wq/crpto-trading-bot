from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.models.execution import ExecutionResult, ExecutionStatus
from app.models.signal import SignalSide, StrategyName, StrategySignal
from app.persistence import PersistenceDatabase
from app.repositories import ActivityRepository


def _signal(signal_id: str = "sig-persist-1") -> StrategySignal:
    return StrategySignal(
        signal_id=signal_id,
        symbol="BTCUSDT",
        strategy=StrategyName.EMA_RSI_ADX_MOMENTUM,
        side=SignalSide.BUY,
        entry_timeframe="5m",
        trend_timeframe="15m",
        signal_time=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
        reference_entry_price=Decimal("100000"),
        ema_fast=Decimal("100100"),
        ema_slow=Decimal("99900"),
        rsi=Decimal("60"),
        adx=Decimal("25"),
        volume=Decimal("120"),
        average_volume=Decimal("100"),
        higher_tf_ema_fast=Decimal("100050"),
        higher_tf_ema_slow=Decimal("99850"),
        higher_tf_ema_fast_previous=Decimal("100000"),
        crossover_age_candles=0,
        confidence=80,
    )


def test_signal_history_survives_repository_recreation(tmp_path) -> None:
    db = PersistenceDatabase(str(tmp_path / "bot.sqlite3"))
    first = ActivityRepository(persistence=db)
    first.record_signal(_signal())

    second = ActivityRepository(persistence=PersistenceDatabase(str(tmp_path / "bot.sqlite3")))
    rows = second.list_signals(limit=10)

    assert len(rows) == 1
    assert rows[0].signal_id == "sig-persist-1"


def test_submitted_signal_ids_survive_restart(tmp_path) -> None:
    db = PersistenceDatabase(str(tmp_path / "bot.sqlite3"))
    result = ExecutionResult(
        status=ExecutionStatus.SUBMITTED,
        signal_id="sig-executed",
        symbol="BTCUSDT",
        side=SignalSide.BUY,
        submitted_at=datetime(2026, 9, 16, 12, 1, tzinfo=timezone.utc),
        order_id="order-1",
    )
    db.record_execution(result)

    reopened = PersistenceDatabase(str(tmp_path / "bot.sqlite3"))
    assert reopened.submitted_signal_ids() == {"sig-executed"}


def test_daily_equity_baseline_survives_restart(tmp_path) -> None:
    db_path = str(tmp_path / "bot.sqlite3")
    day = date(2026, 9, 16)
    first = PersistenceDatabase(db_path)
    first.set_daily_baseline(day, Decimal("10000"))

    reopened = PersistenceDatabase(db_path)
    assert reopened.get_daily_baseline(day) == Decimal("10000")


def test_persistence_status_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/system/persistence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "sqlite"
    assert payload["restart_behavior"] == "manual_start_required"



def test_execution_lifecycle_fields_survive_restart(tmp_path) -> None:
    path = str(tmp_path / "bot.sqlite3")
    db = PersistenceDatabase(path)
    result = ExecutionResult(
        status=ExecutionStatus.UNKNOWN_RECONCILING,
        signal_id="sig-intent",
        execution_intent_id="exec-123",
        risk_decision_id="risk-123",
        request_hash="hash-123",
        symbol="BTCUSDT",
        side=SignalSide.BUY,
        submitted_at=datetime(2026, 9, 16, 12, 1, tzinfo=timezone.utc),
        order_link_id="bot-link-123",
        quantity=Decimal("0.01"),
        price=Decimal("100000"),
        stop_loss=Decimal("99000"),
        take_profit=Decimal("102000"),
        leverage=Decimal("3"),
    )
    db.record_execution(result)

    reopened = PersistenceDatabase(path)
    stored = reopened.get_execution("sig-intent")

    assert stored is not None
    assert stored.execution_intent_id == "exec-123"
    assert stored.risk_decision_id == "risk-123"
    assert stored.request_hash == "hash-123"
    assert stored.status is ExecutionStatus.UNKNOWN_RECONCILING
    assert reopened.submitted_signal_ids() == {"sig-intent"}


def test_writable_health_proves_main_database_writeability(tmp_path) -> None:
    db = PersistenceDatabase(str(tmp_path / "writable.sqlite3"))

    health = db.writable_health()

    assert health["status"] == "ok"
    assert health["database"] == "sqlite"
    assert health["writable"] is True

    # Probe rows are cleaned up; the health check must not accumulate data.
    import sqlite3
    with sqlite3.connect(db.path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM persistence_write_probe"
        ).fetchone()[0]
    assert count == 0
