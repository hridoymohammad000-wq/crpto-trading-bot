from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.candle import SupportedSymbol


class StrategyName(StrEnum):
    EMA_RSI_ADX_MOMENTUM = "EMA_RSI_ADX_MOMENTUM"


class SignalSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class SignalStatus(StrEnum):
    NEW = "NEW"


class StrategyResult(StrEnum):
    SIGNAL = "SIGNAL"
    NO_SIGNAL = "NO_SIGNAL"


class NoSignalReason(StrEnum):
    NO_CROSSOVER = "NO_CROSSOVER"
    ENTRY_WINDOW_EXPIRED = "ENTRY_WINDOW_EXPIRED"
    RSI_FILTER_FAILED = "RSI_FILTER_FAILED"
    ADX_FILTER_FAILED = "ADX_FILTER_FAILED"
    VOLUME_FILTER_FAILED = "VOLUME_FILTER_FAILED"
    CANDLE_CONFIRMATION_FAILED = "CANDLE_CONFIRMATION_FAILED"
    HTF_TREND_FAILED = "HTF_TREND_FAILED"
    HTF_SLOPE_FAILED = "HTF_SLOPE_FAILED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DUPLICATE_SETUP = "DUPLICATE_SETUP"


class IndicatorSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    ema_fast: Decimal | None = None
    ema_slow: Decimal | None = None
    rsi: Decimal | None = None
    adx: Decimal | None = None
    volume: Decimal | None = None
    average_volume: Decimal | None = None
    higher_tf_ema_fast: Decimal | None = None
    higher_tf_ema_slow: Decimal | None = None
    higher_tf_ema_fast_previous: Decimal | None = None


class StrategySignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_id: str
    symbol: SupportedSymbol
    strategy: StrategyName
    side: SignalSide
    entry_timeframe: Literal["5m"]
    trend_timeframe: Literal["15m"]
    signal_time: datetime
    reference_entry_price: Decimal
    ema_fast: Decimal
    ema_slow: Decimal
    rsi: Decimal
    adx: Decimal
    volume: Decimal
    average_volume: Decimal
    higher_tf_ema_fast: Decimal
    higher_tf_ema_slow: Decimal
    higher_tf_ema_fast_previous: Decimal
    crossover_age_candles: int
    confidence: int
    status: SignalStatus = SignalStatus.NEW


class StrategyEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: SupportedSymbol
    strategy: StrategyName = StrategyName.EMA_RSI_ADX_MOMENTUM
    evaluation_time: datetime
    latest_entry_candle_time: datetime | None
    latest_trend_candle_time: datetime | None
    signal: StrategySignal | None = None
    reason_codes: tuple[NoSignalReason, ...] = ()
    indicators: IndicatorSnapshot | None = None
    crossover_age_candles: int | None = None


class StrategyDiagnosticResponse(BaseModel):
    """Stable public representation of one read-only strategy evaluation."""

    model_config = ConfigDict(frozen=True)

    symbol: SupportedSymbol
    strategy: StrategyName
    evaluation_time: datetime
    latest_5m_candle_time: datetime | None
    latest_15m_candle_time: datetime | None
    result: StrategyResult
    side: SignalSide | None
    reference_entry_price: Decimal | None
    confidence: int | None
    reason_codes: tuple[NoSignalReason, ...]
    indicators: IndicatorSnapshot
    crossover_age_candles: int | None
    duplicate_setup: bool

    @classmethod
    def from_evaluation(
        cls, evaluation: StrategyEvaluation
    ) -> "StrategyDiagnosticResponse":
        signal = evaluation.signal
        return cls(
            symbol=evaluation.symbol,
            strategy=evaluation.strategy,
            evaluation_time=evaluation.evaluation_time,
            latest_5m_candle_time=evaluation.latest_entry_candle_time,
            latest_15m_candle_time=evaluation.latest_trend_candle_time,
            result=(
                StrategyResult.SIGNAL if signal is not None else StrategyResult.NO_SIGNAL
            ),
            side=signal.side if signal is not None else None,
            reference_entry_price=(
                signal.reference_entry_price if signal is not None else None
            ),
            confidence=signal.confidence if signal is not None else None,
            reason_codes=evaluation.reason_codes,
            indicators=evaluation.indicators or IndicatorSnapshot(),
            crossover_age_candles=(
                signal.crossover_age_candles
                if signal is not None
                else evaluation.crossover_age_candles
            ),
            duplicate_setup=NoSignalReason.DUPLICATE_SETUP in evaluation.reason_codes,
        )
