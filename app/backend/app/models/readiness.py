from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.models.candle import SupportedSymbol
from app.models.risk import RiskDecisionStatus


class TradingReadinessStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class TradingReadinessReason(StrEnum):
    BLOCKED_ACCOUNT_UNAVAILABLE = "BLOCKED_ACCOUNT_UNAVAILABLE"
    BLOCKED_ACCOUNT_MODE_MISMATCH = "BLOCKED_ACCOUNT_MODE_MISMATCH"
    BLOCKED_AVAILABLE_MARGIN_UNKNOWN = "BLOCKED_AVAILABLE_MARGIN_UNKNOWN"
    BLOCKED_INSUFFICIENT_MARGIN = "BLOCKED_INSUFFICIENT_MARGIN"
    BLOCKED_STARTUP_RECONCILIATION = "BLOCKED_STARTUP_RECONCILIATION"
    BLOCKED_RECONCILIATION_CRITICAL = "BLOCKED_RECONCILIATION_CRITICAL"
    BLOCKED_RECONCILIATION_STALE = "BLOCKED_RECONCILIATION_STALE"
    BLOCKED_DATABASE_UNAVAILABLE = "BLOCKED_DATABASE_UNAVAILABLE"
    BLOCKED_DUPLICATE_RUNTIME = "BLOCKED_DUPLICATE_RUNTIME"
    BLOCKED_UNRESOLVED_EXECUTION = "BLOCKED_UNRESOLVED_EXECUTION"
    BLOCKED_SIGNAL_STALE = "BLOCKED_SIGNAL_STALE"
    BLOCKED_DUPLICATE_SIGNAL = "BLOCKED_DUPLICATE_SIGNAL"
    BLOCKED_COOLDOWN = "BLOCKED_COOLDOWN"
    BLOCKED_EXECUTION_SELECTION = "BLOCKED_EXECUTION_SELECTION"
    BLOCKED_DAILY_LOSS_LIMIT = "BLOCKED_DAILY_LOSS_LIMIT"
    BLOCKED_MAX_POSITIONS = "BLOCKED_MAX_POSITIONS"
    BLOCKED_MAX_OPEN_RISK = "BLOCKED_MAX_OPEN_RISK"
    BLOCKED_RISK_REJECTED = "BLOCKED_RISK_REJECTED"


class TradingReadinessDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: TradingReadinessStatus
    reason_codes: tuple[TradingReadinessReason, ...] = ()
    evaluated_at: datetime
    signal_id: str
    symbol: SupportedSymbol
    signal_age_seconds: float
    risk_status: RiskDecisionStatus
    reconciliation_status: str | None = None
    reconciliation_age_seconds: float | None = None
    available_margin: Decimal | None = None
    account_type: str | None = None
    margin_mode: str | None = None
    database_healthy: bool = False
    reduce_only: bool = False
