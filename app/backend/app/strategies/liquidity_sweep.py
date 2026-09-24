"""Liquidity Sweep Strategy.

Timeframes: 1m for sweep detection, 5m for confirmation.
Detects stop hunts where price wicks beyond key levels then reverses.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.models.candle import Candle, SupportedSymbol
from app.models.signal import (
    NoSignalReason,
    SignalSide,
    StrategyEvaluation,
    StrategyName,
    StrategySignal,
)
from app.strategies.indicators import ema, moving_average

logger = logging.getLogger(__name__)

_SWEEP_THRESHOLD_PCT = Decimal("0.001")  # 0.1% beyond key level


def _find_key_levels(candles: tuple[Candle, ...], lookback: int = 3) -> tuple[list[Decimal], list[Decimal]]:
    """Find swing high and low key levels.

    Returns (resistance_levels, support_levels).
    """
    resistances: list[Decimal] = []
    supports: list[Decimal] = []
    for i in range(lookback, len(candles) - lookback):
        is_high = all(
            candles[i].high >= candles[i + j].high
            for j in range(-lookback, lookback + 1)
            if j != 0
        )
        is_low = all(
            candles[i].low <= candles[i + j].low
            for j in range(-lookback, lookback + 1)
            if j != 0
        )
        if is_high:
            resistances.append(candles[i].high)
        if is_low:
            supports.append(candles[i].low)
    return resistances, supports


class LiquiditySweepStrategy:
    name = StrategyName.LIQUIDITY_SWEEP

    def __init__(self) -> None:
        self._emitted: set[tuple[str, str, datetime, str]] = set()

    def reset(self) -> None:
        self._emitted.clear()

    async def evaluate(
        self,
        symbol: SupportedSymbol,
        fast_candles: tuple[Candle, ...],
        confirm_candles: tuple[Candle, ...],
    ) -> StrategyEvaluation:
        now = datetime.now(timezone.utc)
        fast = self._closed(fast_candles, symbol, "1m")
        confirm = self._closed(confirm_candles, symbol, "5m")

        if len(fast) < 20 or len(confirm) < 20:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=fast[-1].start_time if fast else None,
                latest_trend_candle_time=confirm[-1].start_time if confirm else None,
                reason_codes=(NoSignalReason.INSUFFICIENT_DATA,),
            )

        # Find key levels from 5m candles
        resistances, supports = _find_key_levels(confirm[-20:])

        if not resistances and not supports:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=fast[-1].start_time,
                latest_trend_candle_time=confirm[-1].start_time,
                reason_codes=(NoSignalReason.NO_CROSSOVER,),
            )

        # Check last few 1m candles for sweep
        side: SignalSide | None = None
        levels_swept = 0
        sweep_volume = Decimal(0)

        for candle in fast[-5:]:
            # Support sweep: wick below support, close above
            for support in supports:
                threshold = support * (Decimal(1) - _SWEEP_THRESHOLD_PCT)
                if candle.low < threshold and candle.close > support:
                    side = SignalSide.BUY
                    levels_swept += 1
                    sweep_volume = max(sweep_volume, candle.volume)

            # Resistance sweep: wick above resistance, close below
            for resistance in resistances:
                threshold = resistance * (Decimal(1) + _SWEEP_THRESHOLD_PCT)
                if candle.high > threshold and candle.close < resistance:
                    side = SignalSide.SELL
                    levels_swept += 1
                    sweep_volume = max(sweep_volume, candle.volume)

        if side is None:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=fast[-1].start_time,
                latest_trend_candle_time=confirm[-1].start_time,
                reason_codes=(NoSignalReason.NO_CROSSOVER,),
            )

        # Confirmation: next 1m candle confirms direction
        last_1m = fast[-1]
        if side == SignalSide.BUY and last_1m.close <= last_1m.open:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=fast[-1].start_time,
                latest_trend_candle_time=confirm[-1].start_time,
                reason_codes=(NoSignalReason.NO_CROSSOVER,),
            )
        if side == SignalSide.SELL and last_1m.close >= last_1m.open:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=fast[-1].start_time,
                latest_trend_candle_time=confirm[-1].start_time,
                reason_codes=(NoSignalReason.NO_CROSSOVER,),
            )

        # Duplicate check
        cross_time = fast[-1].start_time
        setup_key = (symbol, self.name, cross_time, side)
        if setup_key in self._emitted:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=fast[-1].start_time,
                latest_trend_candle_time=confirm[-1].start_time,
                reason_codes=(NoSignalReason.DUPLICATE_SETUP,),
            )

        # Confidence
        volumes_5m = tuple(c.volume for c in confirm)
        avg_vol = moving_average(volumes_5m, 20)
        confidence = 75
        if levels_swept > 1:
            confidence += 15
        if avg_vol[-1] is not None and sweep_volume > avg_vol[-1]:
            confidence += 10
        confidence = min(confidence, 100)

        closes_5m = tuple(c.close for c in confirm)
        ema9 = ema(closes_5m, 9)
        ema21 = ema(closes_5m, 21)

        signal = StrategySignal(
            signal_id=str(uuid5(NAMESPACE_URL, ":".join(map(str, setup_key)))),
            symbol=symbol,
            strategy=self.name,
            side=side,
            entry_timeframe="5m",
            trend_timeframe="15m",
            signal_time=now,
            reference_entry_price=confirm[-1].close,
            ema_fast=ema9[-1] or Decimal(0),
            ema_slow=ema21[-1] or Decimal(0),
            rsi=Decimal(0),
            adx=Decimal(0),
            volume=sweep_volume,
            average_volume=avg_vol[-1] or Decimal(0),
            higher_tf_ema_fast=Decimal(0),
            higher_tf_ema_slow=Decimal(0),
            higher_tf_ema_fast_previous=Decimal(0),
            crossover_age_candles=0,
            confidence=confidence,
        )
        self._emitted.add(setup_key)
        return StrategyEvaluation(
            symbol=symbol,
            strategy=self.name,
            evaluation_time=now,
            latest_entry_candle_time=fast[-1].start_time,
            latest_trend_candle_time=confirm[-1].start_time,
            signal=signal,
        )

    @staticmethod
    def _closed(candles: tuple[Candle, ...], symbol: str, tf: str) -> tuple[Candle, ...]:
        by_time = {
            c.start_time: c for c in candles
            if c.is_closed and c.symbol == symbol and c.timeframe == tf
        }
        return tuple(sorted(by_time.values(), key=lambda c: c.start_time))
