"""ICT (Inner Circle Trader) Strategy.

Timeframes: 5m entry, 15m structure, 1H bias.
Signals based on:
  1. Fair Value Gap (FVG)
  2. Order Block detection
  3. Killzone session filter (London 07-10 UTC, NY 13-16 UTC)
  4. HTF Bias via 1H EMA9 vs EMA21
"""

import logging
from datetime import datetime, timedelta, timezone
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

_KILLZONE_LONDON = {7, 8, 9}
_KILLZONE_NY = {13, 14, 15}


class ICTStrategy:
    name = StrategyName.ICT_STRATEGY

    def __init__(self) -> None:
        self._emitted: set[tuple[str, str, datetime, str]] = set()

    def reset(self) -> None:
        self._emitted.clear()

    async def evaluate(
        self,
        symbol: SupportedSymbol,
        entry_candles: tuple[Candle, ...],
        trend_candles: tuple[Candle, ...],
        htf_candles: tuple[Candle, ...],
    ) -> StrategyEvaluation:
        now = datetime.now(timezone.utc)
        entry = self._closed(entry_candles, symbol, "5m")
        trend = self._closed(trend_candles, symbol, "15m")
        htf = self._closed(htf_candles, symbol, "1H")

        if len(entry) < 20 or len(trend) < 10 or len(htf) < 22:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time if entry else None,
                latest_trend_candle_time=trend[-1].start_time if trend else None,
                reason_codes=(NoSignalReason.INSUFFICIENT_DATA,),
            )

        # Killzone filter
        current_hour = now.hour
        in_killzone = current_hour in _KILLZONE_LONDON or current_hour in _KILLZONE_NY
        if not in_killzone:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time,
                latest_trend_candle_time=trend[-1].start_time,
                reason_codes=(NoSignalReason.HTF_TREND_FAILED,),
            )

        # HTF bias from 1H EMA9 vs EMA21
        htf_closes = tuple(c.close for c in htf)
        htf_ema9 = ema(htf_closes, 9)
        htf_ema21 = ema(htf_closes, 21)
        if htf_ema9[-1] is None or htf_ema21[-1] is None:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time,
                latest_trend_candle_time=trend[-1].start_time,
                reason_codes=(NoSignalReason.INSUFFICIENT_DATA,),
            )

        bullish_bias = htf_ema9[-1] > htf_ema21[-1]

        # FVG detection on 5m
        fvg_bull = False
        fvg_bear = False
        for i in range(len(entry) - 3, max(len(entry) - 10, 0), -1):
            if entry[i].high < entry[i + 2].low:
                fvg_bull = True
                break
            if entry[i].low > entry[i + 2].high:
                fvg_bear = True
                break

        # Order Block detection on 5m
        ob_bull = False
        ob_bear = False
        for i in range(len(entry) - 4, max(len(entry) - 12, 0), -1):
            c0, c1, c2, c3 = entry[i], entry[i + 1], entry[i + 2], entry[i + 3]
            # Bullish OB: bearish candle followed by 3 bullish impulse candles
            if c0.close < c0.open and c1.close > c1.open and c2.close > c2.open and c3.close > c3.open:
                if c3.close > c0.high:
                    ob_bull = True
                    break
            # Bearish OB: bullish candle followed by 3 bearish impulse candles
            if c0.close > c0.open and c1.close < c1.open and c2.close < c2.open and c3.close < c3.open:
                if c3.close < c0.low:
                    ob_bear = True
                    break

        # Signal logic
        side: SignalSide | None = None
        if bullish_bias and (fvg_bull or ob_bull):
            side = SignalSide.BUY
        elif not bullish_bias and (fvg_bear or ob_bear):
            side = SignalSide.SELL

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
        confidence = 75
        both_align = (fvg_bull and ob_bull) if side == SignalSide.BUY else (fvg_bear and ob_bear)
        if both_align:
            confidence += 10
        if avg_vol[-1] is not None and volumes_5m[-1] > avg_vol[-1]:
            confidence += 10
        if adx_vals[-1] is not None and adx_vals[-1] > Decimal(25):
            confidence += 5
        confidence = min(confidence, 100)

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
            reference_entry_price=entry[-1].close,
            ema_fast=ema9[-1] or Decimal(0),
            ema_slow=ema21[-1] or Decimal(0),
            rsi=Decimal(0),
            adx=adx_vals[-1] or Decimal(0),
            volume=volumes_5m[-1],
            average_volume=avg_vol[-1] or Decimal(0),
            higher_tf_ema_fast=htf_ema9[-1] or Decimal(0),
            higher_tf_ema_slow=htf_ema21[-1] or Decimal(0),
            higher_tf_ema_fast_previous=htf_ema9[-2] or Decimal(0),
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
