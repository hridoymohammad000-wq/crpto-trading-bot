import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

from app.models.account import AccountSummaryResponse
from app.models.readiness import TradingReadinessReason, TradingReadinessStatus
from app.models.risk import RiskDecision, RiskDecisionStatus, RiskRejectReason
from app.models.signal import SignalSide, StrategyName, StrategySignal
from app.readiness import TradingReadinessService
from app.reconciliation.engine import ReconciliationResult, ReconciliationStatus

NOW = datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)


def make_signal(*, age_seconds: int = 0) -> StrategySignal:
    return StrategySignal(
        signal_id="sig-BTCUSDT",
        symbol="BTCUSDT",
        strategy=StrategyName.EMA_RSI_ADX_MOMENTUM,
        side=SignalSide.BUY,
        entry_timeframe="5m",
        trend_timeframe="15m",
        signal_time=NOW - timedelta(seconds=age_seconds),
        reference_entry_price=Decimal("100"),
        ema_fast=Decimal("101"),
        ema_slow=Decimal("99"),
        rsi=Decimal("60"),
        adx=Decimal("30"),
        volume=Decimal("120"),
        average_volume=Decimal("100"),
        higher_tf_ema_fast=Decimal("102"),
        higher_tf_ema_slow=Decimal("98"),
        higher_tf_ema_fast_previous=Decimal("101"),
        crossover_age_candles=0,
        confidence=90,
    )


def risk_ready() -> RiskDecision:
    return RiskDecision(
        status=RiskDecisionStatus.READY,
        signal_id="sig-BTCUSDT",
        symbol="BTCUSDT",
        side=SignalSide.BUY,
        evaluated_at=NOW,
        entry=Decimal("100"),
        quantity=Decimal("1"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        risk_reward_ratio=Decimal("2"),
        leverage=Decimal("3"),
    )


def risk_rejected(reason: RiskRejectReason) -> RiskDecision:
    return RiskDecision(
        status=RiskDecisionStatus.REJECTED,
        signal_id="sig-BTCUSDT",
        symbol="BTCUSDT",
        side=SignalSide.BUY,
        evaluated_at=NOW,
        entry=Decimal("100"),
        reason=reason,
    )


def account(available=Decimal("900")) -> AccountSummaryResponse:
    return AccountSummaryResponse(
        balance=Decimal("1000"),
        equity=Decimal("1000"),
        margin_balance=Decimal("1000"),
        available_margin=available,
        available_balance=available,
        available_trading_capacity=available,
        capacity_source="TOTAL_AVAILABLE_BALANCE",
        unrealized_pnl=Decimal("0"),
        account_type="UNIFIED",
        unified_margin_status=5,
        margin_mode="REGULAR_MARGIN",
        coins=[],
    )


def reconciliation(status=ReconciliationStatus.SYNCED, *, age_seconds=0):
    return ReconciliationResult(
        status=status,
        last_reconciled_at=NOW - timedelta(seconds=age_seconds),
        mismatches=[],
        wallet={},
        positions={},
        orders={},
        local_state={},
    )


def build_service(*, summary=None, recon=None, db_ok=True):
    account_service = Mock()
    account_service.get_summary = AsyncMock(return_value=summary or account())
    reconciliation_engine = Mock()
    reconciliation_engine.get_latest_result = AsyncMock(
        return_value=recon or reconciliation()
    )
    persistence = Mock()
    persistence.unresolved_executions.return_value = []
    if db_ok:
        persistence.writable_health.return_value = {
            "status": "ok",
            "writable": True,
        }
    else:
        persistence.writable_health.side_effect = RuntimeError("db down")
    return TradingReadinessService(
        account_service,
        reconciliation_engine,
        persistence,
        max_signal_age_seconds=600,
        max_reconciliation_age_seconds=60,
    )


def evaluate(service, signal=None, risk=None, **kwargs):
    return asyncio.run(
        service.evaluate(
            signal or make_signal(),
            risk or risk_ready(),
            execution_allowed=kwargs.pop("execution_allowed", True),
            now=NOW,
            **kwargs,
        )
    )


def test_ready_when_all_checks_pass():
    decision = evaluate(build_service())
    assert decision.status is TradingReadinessStatus.READY
    assert decision.reason_codes == ()
    assert decision.database_healthy is True
    assert decision.available_margin == Decimal("900")


def test_unknown_available_margin_blocks_new_entry():
    decision = evaluate(build_service(summary=account(None)))
    assert decision.status is TradingReadinessStatus.BLOCKED
    assert TradingReadinessReason.BLOCKED_AVAILABLE_MARGIN_UNKNOWN in decision.reason_codes


def test_unknown_available_margin_does_not_block_reduce_only_by_itself():
    decision = evaluate(build_service(summary=account(None)), reduce_only=True)
    assert TradingReadinessReason.BLOCKED_AVAILABLE_MARGIN_UNKNOWN not in decision.reason_codes
    assert decision.status is TradingReadinessStatus.READY


def test_critical_reconciliation_warns_only():
    decision = evaluate(
        build_service(recon=reconciliation(ReconciliationStatus.POSITION_MISMATCH))
    )
    assert decision.status is TradingReadinessStatus.READY
    assert TradingReadinessReason.BLOCKED_RECONCILIATION_CRITICAL not in decision.reason_codes


def test_stale_reconciliation_blocks():
    decision = evaluate(build_service(recon=reconciliation(age_seconds=61)))
    assert TradingReadinessReason.BLOCKED_RECONCILIATION_STALE in decision.reason_codes


def test_database_failure_blocks():
    decision = evaluate(build_service(db_ok=False))
    assert TradingReadinessReason.BLOCKED_DATABASE_UNAVAILABLE in decision.reason_codes


def test_stale_duplicate_cooldown_and_selection_are_all_reported():
    decision = evaluate(
        build_service(),
        signal=make_signal(age_seconds=601),
        execution_allowed=False,
        duplicate_signal=True,
        cooldown_active=True,
    )
    assert decision.status is TradingReadinessStatus.BLOCKED
    assert TradingReadinessReason.BLOCKED_SIGNAL_STALE in decision.reason_codes
    assert TradingReadinessReason.BLOCKED_DUPLICATE_SIGNAL in decision.reason_codes
    assert TradingReadinessReason.BLOCKED_COOLDOWN in decision.reason_codes
    assert TradingReadinessReason.BLOCKED_EXECUTION_SELECTION in decision.reason_codes


def test_risk_daily_loss_maps_to_readiness_reasons():
    decision = evaluate(
        build_service(),
        risk=risk_rejected(RiskRejectReason.DAILY_LOSS_LIMIT),
    )
    assert TradingReadinessReason.BLOCKED_RISK_REJECTED in decision.reason_codes
    assert TradingReadinessReason.BLOCKED_DAILY_LOSS_LIMIT in decision.reason_codes


def test_risk_max_positions_maps_to_readiness_reason():
    decision = evaluate(
        build_service(),
        risk=risk_rejected(RiskRejectReason.MAX_ACTIVE_POSITIONS),
    )
    assert TradingReadinessReason.BLOCKED_MAX_POSITIONS in decision.reason_codes


def test_startup_reconciliation_incomplete_blocks_entry():
    decision = evaluate(
        build_service(),
        startup_reconciliation_complete=False,
    )
    assert decision.status is TradingReadinessStatus.BLOCKED
    assert (
        TradingReadinessReason.BLOCKED_STARTUP_RECONCILIATION
        in decision.reason_codes
    )


def test_wrong_account_mode_blocks_entry():
    bad = account()
    bad = bad.model_copy(update={"account_type": "UNIFIED", "margin_mode": None})
    # Missing mode alone is not treated as an environment mismatch by the model;
    # verify the hard environment/account-type guard with a constructed payload.
    object.__setattr__(bad, "environment", "live")
    decision = evaluate(build_service(summary=bad))
    assert decision.status is TradingReadinessStatus.BLOCKED
    assert TradingReadinessReason.BLOCKED_ACCOUNT_MODE_MISMATCH in decision.reason_codes


def test_unresolved_execution_blocks_new_entry():
    service = build_service()
    service._persistence.unresolved_executions.return_value = [object()]
    decision = evaluate(service)
    assert decision.status is TradingReadinessStatus.BLOCKED
    assert (
        TradingReadinessReason.BLOCKED_UNRESOLVED_EXECUTION
        in decision.reason_codes
    )


def test_unresolved_execution_does_not_block_reduce_only_exit():
    service = build_service()
    service._persistence.unresolved_executions.return_value = [object()]
    decision = evaluate(service, reduce_only=True)
    assert (
        TradingReadinessReason.BLOCKED_UNRESOLVED_EXECUTION
        not in decision.reason_codes
    )


def test_database_failure_does_not_block_reduce_only_exit():
    decision = evaluate(build_service(db_ok=False), reduce_only=True)
    assert TradingReadinessReason.BLOCKED_DATABASE_UNAVAILABLE not in decision.reason_codes
    assert decision.status is TradingReadinessStatus.READY
    assert decision.database_healthy is False


def test_protection_mismatch_warns_only_for_new_entry():
    decision = evaluate(
        build_service(
            recon=reconciliation(ReconciliationStatus.PROTECTION_MISMATCH)
        )
    )
    assert decision.status is TradingReadinessStatus.READY
    assert (
        TradingReadinessReason.BLOCKED_RECONCILIATION_CRITICAL
        not in decision.reason_codes
    )
