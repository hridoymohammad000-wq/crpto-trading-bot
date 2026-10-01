from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field

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

    @computed_field
    @property
    def expires_at(self) -> datetime:
        from datetime import timedelta
        from app.core.config import settings
        return self.signal_time + timedelta(seconds=settings.SIGNAL_MAX_AGE_SECONDS)

    @computed_field
    @property
    def is_expired(self) -> bool:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) >= self.expires_at

    @computed_field
    @property
    def age_seconds(self) -> float:
        from datetime import datetime, timezone
        return (datetime.now(timezone.utc) - self.signal_time).total_seconds()


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
    strategy: str | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    exit_reason: str | None = None
    diagnostic_reason: str | None = None

    # Intratrade path diagnostics.
    mae_price: Decimal | None = None
    mfe_price: Decimal | None = None
    mae_pct: Decimal | None = None
    mfe_pct: Decimal | None = None
    mae_r: Decimal | None = None
    mfe_r: Decimal | None = None
    sl_distance: Decimal | None = None
    sl_distance_atr: Decimal | None = None
    mae_at: datetime | None = None
    mfe_at: datetime | None = None
    root_cause: str | None = None
    root_cause_evidence: str | None = None
    excursion_status: str | None = None


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
