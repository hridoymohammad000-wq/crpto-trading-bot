"""SMC (Smart Money Concepts) Strategy.

Timeframes: 5m entry, 15m structure.
Signals based on:
  1. Break of Structure (BOS)
  2. Change of Character (CHOCH)
  3. Premium/Discount zones
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.models.candle import Candle, SupportedSymbol
from app.models.signal import (
    IndicatorSnapshot,
    NoSignalReason,
    SignalSide,
    StrategyEvaluation,
    StrategyName,
    StrategySignal,
)
from app.strategies.indicators import adx, ema, moving_average

logger = logging.getLogger(__name__)


def _find_swing_highs(candles: tuple[Candle, ...], lookback: int = 3) -> list[Decimal]:
    """Find local swing highs with N-candle confirmation on each side."""
    highs: list[Decimal] = []
    for i in range(lookback, len(candles) - lookback):
        is_high = all(
            candles[i].high >= candles[i + j].high
            for j in range(-lookback, lookback + 1)
            if j != 0
        )
        if is_high:
            highs.append(candles[i].high)
    return highs


def _find_swing_lows(candles: tuple[Candle, ...], lookback: int = 3) -> list[Decimal]:
    """Find local swing lows with N-candle confirmation on each side."""
    lows: list[Decimal] = []
    for i in range(lookback, len(candles) - lookback):
        is_low = all(
            candles[i].low <= candles[i + j].low
            for j in range(-lookback, lookback + 1)
            if j != 0
        )
        if is_low:
            lows.append(candles[i].low)
    return lows


class SMCStrategy:
    name = StrategyName.SMC_STRATEGY

    def __init__(self) -> None:
        self._emitted: set[tuple[str, str, datetime, str]] = set()

    def reset(self) -> None:
        self._emitted.clear()

    async def evaluate(
        self,
        symbol: SupportedSymbol,
        entry_candles: tuple[Candle, ...],
        trend_candles: tuple[Candle, ...],
    ) -> StrategyEvaluation:
        now = datetime.now(timezone.utc)
        entry = self._closed(entry_candles, symbol, "5m")
        trend = self._closed(trend_candles, symbol, "15m")

        if len(entry) < 20 or len(trend) < 10:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time if entry else None,
                latest_trend_candle_time=trend[-1].start_time if trend else None,
                reason_codes=(NoSignalReason.INSUFFICIENT_DATA,),
            )

        swing_highs = _find_swing_highs(entry[-20:])
        swing_lows = _find_swing_lows(entry[-20:])

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time,
                latest_trend_candle_time=trend[-1].start_time,
                reason_codes=(NoSignalReason.NO_CROSSOVER,),
            )

        current_close = entry[-1].close
        prev_swing_high = swing_highs[-1]
        prev_swing_low = swing_lows[-1]

        # BOS detection
        bos_bull = current_close > prev_swing_high
        bos_bear = current_close < prev_swing_low

        # CHOCH detection: trend reversal
        choch_bull = False
        choch_bear = False
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            # Downtrend (lower highs) then break above
            if swing_highs[-1] < swing_highs[-2] and current_close > swing_highs[-1]:
                choch_bull = True
            # Uptrend (higher lows) then break below
            if swing_lows[-1] > swing_lows[-2] and current_close < swing_lows[-1]:
                choch_bear = True

        # Premium/Discount zone
        range_high = max(swing_highs[-2:])
        range_low = min(swing_lows[-2:])
        midpoint = (range_high + range_low) / Decimal(2)
        in_discount = current_close < midpoint
        in_premium = current_close > midpoint

        # Signal logic
        side: SignalSide | None = None
        is_choch = False
        if (bos_bull or choch_bull) and in_discount:
            side = SignalSide.BUY
            is_choch = choch_bull
        elif (bos_bear or choch_bear) and in_premium:
            side = SignalSide.SELL
            is_choch = choch_bear

        if side is None:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time,
                latest_trend_candle_time=trend[-1].start_time,
                reason_codes=(NoSignalReason.NO_CROSSOVER,),
            )

        # Duplicate check
        cross_time = entry[-1].start_time
        setup_key = (symbol, self.name, cross_time, side)
        if setup_key in self._emitted:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time,
                latest_trend_candle_time=trend[-1].start_time,
                reason_codes=(NoSignalReason.DUPLICATE_SETUP,),
            )

        # Confidence
        closes_5m = tuple(c.close for c in entry)
        volumes_5m = tuple(c.volume for c in entry)
        highs_5m = tuple(c.high for c in entry)
        lows_5m = tuple(c.low for c in entry)
        avg_vol = moving_average(volumes_5m, 20)
        adx_vals = adx(highs_5m, lows_5m, closes_5m, 14)
        ema9 = ema(closes_5m, 9)
        ema21 = ema(closes_5m, 21)

        confidence = 70
        if is_choch:
            confidence += 15
        if avg_vol[-1] is not None and volumes_5m[-1] > avg_vol[-1] * Decimal("1.5"):
            confidence += 10
        if adx_vals[-1] is not None and adx_vals[-1] > Decimal(20):
            confidence += 5
        confidence = min(confidence, 100)

        # Build trend EMA from 15m
        trend_closes = tuple(c.close for c in trend)
        trend_ema9 = ema(trend_closes, 9)
        trend_ema21 = ema(trend_closes, 21)

        signal = StrategySignal(
            signal_id=str(uuid5(NAMESPACE_URL, ":".join(map(str, setup_key)))),
            symbol=symbol,
            strategy=self.name,
            side=side,
            entry_timeframe="5m",
            trend_timeframe="15m",
            signal_time=now,
            reference_entry_price=current_close,
            ema_fast=ema9[-1] or Decimal(0),
            ema_slow=ema21[-1] or Decimal(0),
            rsi=Decimal(0),
            adx=adx_vals[-1] or Decimal(0),
            volume=volumes_5m[-1],
            average_volume=avg_vol[-1] or Decimal(0),
            higher_tf_ema_fast=trend_ema9[-1] or Decimal(0),
            higher_tf_ema_slow=trend_ema21[-1] or Decimal(0),
            higher_tf_ema_fast_previous=trend_ema9[-2] or Decimal(0) if len(trend_ema9) >= 2 else Decimal(0),
            crossover_age_candles=0,
            confidence=confidence,
        )
        self._emitted.add(setup_key)
        return StrategyEvaluation(
            symbol=symbol,
            strategy=self.name,
            evaluation_time=now,
            latest_entry_candle_time=entry[-1].start_time,
            latest_trend_candle_time=trend[-1].start_time,
            signal=signal,
        )

    @staticmethod
    def _closed(candles: tuple[Candle, ...], symbol: str, tf: str) -> tuple[Candle, ...]:
        by_time = {
            c.start_time: c for c in candles
            if c.is_closed and c.symbol == symbol and c.timeframe == tf
        }
        return tuple(sorted(by_time.values(), key=lambda c: c.start_time))
