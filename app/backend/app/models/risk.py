from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.models.candle import SupportedSymbol
from app.models.signal import SignalSide


class RiskDecisionStatus(StrEnum):
    READY = "READY"
    REJECTED = "REJECTED"


class RiskRejectReason(StrEnum):
    INVALID_ACCOUNT_EQUITY = "INVALID_ACCOUNT_EQUITY"
    INSUFFICIENT_AVAILABLE_BALANCE = "INSUFFICIENT_AVAILABLE_BALANCE"
    MAX_ACTIVE_POSITIONS = "MAX_ACTIVE_POSITIONS"
    DUPLICATE_SYMBOL_POSITION = "DUPLICATE_SYMBOL_POSITION"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    INSUFFICIENT_STRUCTURE_DATA = "INSUFFICIENT_STRUCTURE_DATA"
    INVALID_STOP_LOSS = "INVALID_STOP_LOSS"
    INVALID_TAKE_PROFIT = "INVALID_TAKE_PROFIT"
    MINIMUM_RR_NOT_MET = "MINIMUM_RR_NOT_MET"
    INVALID_POSITION_SIZE = "INVALID_POSITION_SIZE"
    LEVERAGE_LIMIT_EXCEEDED = "LEVERAGE_LIMIT_EXCEEDED"
    MAX_OPEN_RISK_EXCEEDED = "MAX_OPEN_RISK_EXCEEDED"
    OPEN_POSITION_RISK_UNKNOWN = "OPEN_POSITION_RISK_UNKNOWN"


class RiskDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: RiskDecisionStatus
    signal_id: str
    symbol: SupportedSymbol
    side: SignalSide
    evaluated_at: datetime
    reason: RiskRejectReason | None = None
    entry: Decimal
    quantity: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    risk_reward_ratio: Decimal | None = None
    leverage: Decimal | None = None
    account_equity: Decimal | None = None
    available_balance: Decimal | None = None
    risk_amount: Decimal | None = None
    active_positions: int = 0
    daily_drawdown_pct: Decimal | None = None
    portfolio_open_risk_before: Decimal | None = None
    portfolio_open_risk_after: Decimal | None = None
    max_open_risk_amount: Decimal | None = None
    fee_slippage_allowance: Decimal | None = None
