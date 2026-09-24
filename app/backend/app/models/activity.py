from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.candle import SupportedSymbol
from app.models.execution import ExecutionStatus
from app.models.risk import RiskDecisionStatus
from app.models.signal import SignalSide, StrategyName


class SignalActivityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_id: str
    symbol: SupportedSymbol
    strategy: StrategyName
    side: SignalSide
    signal_time: datetime
    reference_entry_price: Decimal
    confidence: int
    risk_status: RiskDecisionStatus | None = None
    execution_status: ExecutionStatus | None = None
    order_id: str | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None


class ClosedTradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    side: Literal["LONG", "SHORT"]
    quantity: Decimal
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    realized_pnl: Decimal
    open_fee: Decimal | None = None
    close_fee: Decimal | None = None
    order_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TradeStatsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate_pct: Decimal
    total_realized_pnl: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    average_pnl: Decimal
    profit_factor: Decimal | None = None
