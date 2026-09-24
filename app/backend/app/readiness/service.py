import logging
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

from app.account import AccountService
from app.models.readiness import (
    TradingReadinessDecision,
    TradingReadinessReason,
    TradingReadinessStatus,
)
from app.models.risk import RiskDecision, RiskDecisionStatus, RiskRejectReason
from app.models.signal import StrategySignal
from app.persistence import PersistenceDatabase
from app.reconciliation import ReconciliationEngine, ReconciliationStatus


class TradingReadinessService:
    """Final permission gate for introducing new exchange exposure.

    Reconciliation answers whether exchange/local state agree. Readiness answers
    whether this specific execution intent may proceed now. The service fails
    closed for new exposure when account capacity, reconciliation freshness, or
    durable local storage cannot be trusted.
    """

    def __init__(
        self,
        account_service: AccountService,
        reconciliation_engine: ReconciliationEngine,
        persistence: PersistenceDatabase,
        *,
        runtime_leadership: object | None = None,
        max_signal_age_seconds: float = 10 * 60,
        max_reconciliation_age_seconds: float = 60.0,
    ) -> None:
        if max_signal_age_seconds <= 0:
            raise ValueError("max_signal_age_seconds must be positive")
        if max_reconciliation_age_seconds <= 0:
            raise ValueError("max_reconciliation_age_seconds must be positive")
        self._account = account_service
        self._reconciliation = reconciliation_engine
        self._persistence = persistence
        self._runtime_leadership = runtime_leadership
        self.max_signal_age_seconds = max_signal_age_seconds
        self.max_reconciliation_age_seconds = max_reconciliation_age_seconds
        self._last_decision: TradingReadinessDecision | None = None

    @property
    def last_decision(self) -> TradingReadinessDecision | None:
        return self._last_decision

    async def evaluate(
        self,
        signal: StrategySignal,
        risk_decision: RiskDecision,
        *,
        execution_allowed: bool,
        cooldown_active: bool = False,
        duplicate_signal: bool = False,
        reduce_only: bool = False,
        startup_reconciliation_complete: bool = True,
        now: datetime | None = None,
    ) -> TradingReadinessDecision:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        signal_time = signal.signal_time
        if signal_time.tzinfo is None:
            signal_time = signal_time.replace(tzinfo=timezone.utc)
        signal_age = max(0.0, (now - signal_time).total_seconds())

        reasons: list[TradingReadinessReason] = []
        reconciliation_status: str | None = None
        reconciliation_age: float | None = None
        available_margin: Decimal | None = None
        account_type: str | None = None
        margin_mode: str | None = None
        database_healthy = False

        if not execution_allowed:
            reasons.append(TradingReadinessReason.BLOCKED_EXECUTION_SELECTION)
        if not startup_reconciliation_complete:
            reasons.append(TradingReadinessReason.BLOCKED_STARTUP_RECONCILIATION)
        if cooldown_active:
            reasons.append(TradingReadinessReason.BLOCKED_COOLDOWN)
        if duplicate_signal:
            reasons.append(TradingReadinessReason.BLOCKED_DUPLICATE_SIGNAL)
        if signal_age > self.max_signal_age_seconds:
            reasons.append(TradingReadinessReason.BLOCKED_SIGNAL_STALE)

        if (
            not reduce_only
            and self._runtime_leadership is not None
            and not bool(getattr(self._runtime_leadership, "is_owner", False))
        ):
            reasons.append(TradingReadinessReason.BLOCKED_DUPLICATE_RUNTIME)

        if risk_decision.status is not RiskDecisionStatus.READY:
            reasons.append(TradingReadinessReason.BLOCKED_RISK_REJECTED)
            if risk_decision.reason is RiskRejectReason.DAILY_LOSS_LIMIT:
                reasons.append(TradingReadinessReason.BLOCKED_DAILY_LOSS_LIMIT)
            elif risk_decision.reason is RiskRejectReason.MAX_ACTIVE_POSITIONS:
                reasons.append(TradingReadinessReason.BLOCKED_MAX_POSITIONS)
            elif risk_decision.reason in {
                RiskRejectReason.MAX_OPEN_RISK_EXCEEDED,
                RiskRejectReason.OPEN_POSITION_RISK_UNKNOWN,
            }:
                reasons.append(TradingReadinessReason.BLOCKED_MAX_OPEN_RISK)
            elif risk_decision.reason is RiskRejectReason.INSUFFICIENT_AVAILABLE_BALANCE:
                reasons.append(TradingReadinessReason.BLOCKED_INSUFFICIENT_MARGIN)

        try:
            account = await self._account.get_summary()
            available_margin = account.available_trading_capacity
            account_type = account.account_type
            margin_mode = account.margin_mode
            if account.environment != "demo" or account.account_type != "UNIFIED":
                reasons.append(TradingReadinessReason.BLOCKED_ACCOUNT_MODE_MISMATCH)
            if not reduce_only:
                if available_margin is None or not available_margin.is_finite():
                    reasons.append(
                        TradingReadinessReason.BLOCKED_AVAILABLE_MARGIN_UNKNOWN
                    )
                elif available_margin <= 0:
                    reasons.append(TradingReadinessReason.BLOCKED_INSUFFICIENT_MARGIN)
        except Exception:
            reasons.append(TradingReadinessReason.BLOCKED_ACCOUNT_UNAVAILABLE)

        try:
            recon = await self._reconciliation.get_latest_result()
            reconciliation_status = recon.status.value
            if recon.last_reconciled_at is None:
                reasons.append(TradingReadinessReason.BLOCKED_RECONCILIATION_STALE)
            else:
                recon_time = recon.last_reconciled_at
                if recon_time.tzinfo is None:
                    recon_time = recon_time.replace(tzinfo=timezone.utc)
                reconciliation_age = max(0.0, (now - recon_time).total_seconds())
                if reconciliation_age > self.max_reconciliation_age_seconds:
                    reasons.append(TradingReadinessReason.BLOCKED_RECONCILIATION_STALE)
            if recon.status is not ReconciliationStatus.SYNCED:
                # Warn only — do not hard-block on Demo API reconciliation mismatch.
                # BLOCKED_RECONCILIATION_CRITICAL is logged but not added to reasons
                # so a transient mismatch does not kill the entire trading session.
                logger.warning(
                    "Reconciliation status is %s (not SYNCED) for signal %s — proceeding with caution",
                    recon.status.value,
                    signal.signal_id,
                )
        except Exception:
            reasons.append(TradingReadinessReason.BLOCKED_RECONCILIATION_CRITICAL)

        try:
            health = self._persistence.writable_health()
            database_healthy = (
                health.get("status") == "ok"
                and health.get("writable") is True
            )
            if not reduce_only and self._persistence.unresolved_executions():
                reasons.append(
                    TradingReadinessReason.BLOCKED_UNRESOLVED_EXECUTION
                )
        except Exception:
            database_healthy = False

        # A persistence failure must fail closed for any new/increasing
        # exposure. Risk-reducing reduceOnly exits are intentionally exempt
        # from this entry gate so an emergency close is not prevented solely
        # because local storage is unhealthy.
        if not database_healthy and not reduce_only:
            reasons.append(TradingReadinessReason.BLOCKED_DATABASE_UNAVAILABLE)

        # Keep reason ordering deterministic and remove duplicates.
        reason_codes = tuple(dict.fromkeys(reasons))
        decision = TradingReadinessDecision(
            status=(
                TradingReadinessStatus.READY
                if not reason_codes
                else TradingReadinessStatus.BLOCKED
            ),
            reason_codes=reason_codes,
            evaluated_at=now,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            signal_age_seconds=signal_age,
            risk_status=risk_decision.status,
            reconciliation_status=reconciliation_status,
            reconciliation_age_seconds=reconciliation_age,
            available_margin=available_margin,
            account_type=account_type,
            margin_mode=margin_mode,
            database_healthy=database_healthy,
            reduce_only=reduce_only,
        )
        self._last_decision = decision
        return decision
