from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.models.candle import SupportedSymbol
from app.models.signal import SignalSide


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    UNKNOWN_RECONCILING = "UNKNOWN_RECONCILING"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


NON_TERMINAL_EXECUTION_STATUSES = frozenset(
    {
        ExecutionStatus.PENDING,
        ExecutionStatus.SUBMITTED,
        ExecutionStatus.ACKNOWLEDGED,
        ExecutionStatus.PARTIALLY_FILLED,
        ExecutionStatus.UNKNOWN_RECONCILING,
    }
)


class ExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ExecutionStatus
    signal_id: str
    symbol: SupportedSymbol
    side: SignalSide
    submitted_at: datetime
    execution_intent_id: str | None = None
    risk_decision_id: str | None = None
    request_hash: str | None = None
    order_id: str | None = None
    order_link_id: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    leverage: Decimal | None = None
    cumulative_filled_quantity: Decimal | None = None
    average_fill_price: Decimal | None = None
    message: str | None = None
