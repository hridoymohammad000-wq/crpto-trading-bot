from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


SupportedSymbol = str
SupportedTimeframe = Literal["1m", "5m", "15m"]


class Candle(BaseModel):
    """Immutable normalized candle with a timezone-aware UTC start time."""

    model_config = ConfigDict(frozen=True)

    symbol: SupportedSymbol
    timeframe: SupportedTimeframe
    start_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal
    is_closed: bool

    @field_validator("start_time")
    @classmethod
    def normalize_start_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_market_values(self) -> Self:
        values = (
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            self.turnover,
        )
        if not all(value.is_finite() for value in values):
            raise ValueError("candle numeric values must be finite")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to OHLC values")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to OHLC values")
        if self.volume < 0 or self.turnover < 0:
            raise ValueError("volume and turnover must be non-negative")
        return self
