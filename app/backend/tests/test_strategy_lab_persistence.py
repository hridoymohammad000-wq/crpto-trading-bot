from datetime import datetime, timezone
from decimal import Decimal

from app.models.signal import SignalSide, StrategyName, StrategySignal
from app.persistence import PersistenceDatabase
from app.strategies.lab_repository import StrategyLabRepository
from app.strategies.lab_service import StrategyLabService


def _signal(signal_id: str = "lab-signal-1") -> StrategySignal:
    return StrategySignal(
        signal_id=signal_id,
        symbol="BTCUSDT",
        strategy=StrategyName.ICT_STRATEGY,
        side=SignalSide.BUY,
        entry_timeframe="5m",
        trend_timeframe="15m",
        signal_time=datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
        reference_entry_price=Decimal("100"),
        ema_fast=Decimal("101"),
        ema_slow=Decimal("99"),
        rsi=Decimal("60"),
        adx=Decimal("25"),
        volume=Decimal("120"),
        average_volume=Decimal("100"),
        higher_tf_ema_fast=Decimal("101"),
        higher_tf_ema_slow=Decimal("99"),
        higher_tf_ema_fast_previous=Decimal("100"),
        crossover_age_candles=0,
        confidence=90,
    )


def test_lab_repository_persists_and_deduplicates_signal(tmp_path) -> None:
    repository = StrategyLabRepository(
        PersistenceDatabase(str(tmp_path / "lab.sqlite3"))
    )

    assert repository.save_signal(_signal()) is True
    assert repository.save_signal(_signal()) is False

    rows = repository.list_signals(limit=10)
    assert len(rows) == 1
    assert rows[0]["signal_id"] == "lab-signal-1"
    assert rows[0]["strategy"] == "ICT_STRATEGY"
    assert rows[0]["status"] == "OPEN"


def test_lab_mark_to_market_updates_buy_pnl(tmp_path) -> None:
    repository = StrategyLabRepository(
        PersistenceDatabase(str(tmp_path / "lab.sqlite3"))
    )
    repository.save_signal(_signal())

    service = StrategyLabService([], repository=repository)
    updated = service.mark_open_signals({"BTCUSDT": Decimal("105")})

    assert updated == 1
    row = repository.list_signals(limit=1)[0]
    assert Decimal(str(row["current_price"])) == Decimal("102.00")
    assert Decimal(str(row["pnl_pct"])) == Decimal("2.00")
    assert row["last_marked_at"] is not None


def test_lab_performance_summarizes_marked_signals(tmp_path) -> None:
    repository = StrategyLabRepository(
        PersistenceDatabase(str(tmp_path / "lab.sqlite3"))
    )
    repository.save_signal(_signal())

    service = StrategyLabService([], repository=repository)
    service.mark_open_signals({"BTCUSDT": Decimal("105")})

    performance = repository.performance()
    assert len(performance) == 1
    summary = performance[0]
    assert summary["strategy"] == "ICT_STRATEGY"
    assert summary["total_signals"] == 1
    assert summary["marked_signals"] == 1
    assert summary["positive_marks"] == 1
    assert Decimal(str(summary["avg_pnl_pct"])) == Decimal("2.00")


def test_lab_strategy_fund_starts_at_100_and_risks_one_percent(tmp_path) -> None:
    repository = StrategyLabRepository(
        PersistenceDatabase(str(tmp_path / "lab.sqlite3"))
    )
    repository.save_signal(_signal())

    row = repository.list_signals(limit=1)[0]

    assert Decimal(str(row["fund_starting_balance"])) == Decimal("100")
    assert Decimal(str(row["risk_pct"])) == Decimal("1")
    assert Decimal(str(row["risk_amount"])) == Decimal("1")
    assert Decimal(str(row["position_size"])) == Decimal("1")


def test_lab_tp_hit_updates_balance_to_102_and_two_r(tmp_path) -> None:
    repository = StrategyLabRepository(
        PersistenceDatabase(str(tmp_path / "lab.sqlite3"))
    )
    repository.save_signal(_signal())

    service = StrategyLabService([], repository=repository)
    updated = service.mark_open_signals({"BTCUSDT": Decimal("103")})

    assert updated == 1

    row = repository.list_signals(limit=1)[0]
    assert row["status"] == "TP_HIT"
    assert Decimal(str(row["exit_price"])) == Decimal("102")
    assert Decimal(str(row["pnl_usdt"])) == Decimal("2")
    assert Decimal(str(row["r_multiple"])) == Decimal("2")
    assert Decimal(str(row["balance_after_close"])) == Decimal("102")

    perf = repository.performance()[0]
    assert Decimal(str(perf["starting_balance"])) == Decimal("100")
    assert Decimal(str(perf["realized_pnl_usdt"])) == Decimal("2")
    assert Decimal(str(perf["current_equity"])) == Decimal("102")
    assert Decimal(str(perf["return_pct"])) == Decimal("2")

