"""AMD (Accumulation, Manipulation, Distribution) Strategy.

Session-based strategy using Asia range to detect manipulation and distribution.
UTC sessions:
  - Asia: 00:00-07:00 UTC (accumulation range)
  - London: 07:00-10:00 UTC (manipulation)
  - NY: 13:00-17:00 UTC (distribution)
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

_ASIA_START_HOUR = 0
_ASIA_END_HOUR = 7
_LONDON_START_HOUR = 7
_LONDON_END_HOUR = 10
_SWEEP_MIN_PCT = Decimal("0.005")  # 0.5% beyond range


class AMDStrategy:
    name = StrategyName.AMD_STRATEGY

    def __init__(self) -> None:
        self._emitted: set[tuple[str, str, datetime, str]] = set()

    def reset(self) -> None:
        self._emitted.clear()

    async def evaluate(
        self,
        symbol: SupportedSymbol,
        entry_candles: tuple[Candle, ...],
        htf_candles: tuple[Candle, ...],
    ) -> StrategyEvaluation:
        now = datetime.now(timezone.utc)
        entry = self._closed(entry_candles, symbol, "5m")
        htf = self._closed(htf_candles, symbol, "1H")

        if len(entry) < 50 or len(htf) < 24:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time if entry else None,
                latest_trend_candle_time=htf[-1].start_time if htf else None,
                reason_codes=(NoSignalReason.INSUFFICIENT_DATA,),
            )

        # Find Asia range from 1H candles (00:00-07:00 UTC today)
        today = now.date()
        asia_candles = [
            c for c in htf
            if c.start_time.date() == today
            and _ASIA_START_HOUR <= c.start_time.hour < _ASIA_END_HOUR
        ]
        if len(asia_candles) < 2:
            # Try yesterday if early in the day
            from datetime import timedelta
            yesterday = today - timedelta(days=1)
            asia_candles = [
                c for c in htf
                if c.start_time.date() == yesterday
                and _ASIA_START_HOUR <= c.start_time.hour < _ASIA_END_HOUR
            ]

        if len(asia_candles) < 2:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time,
                latest_trend_candle_time=htf[-1].start_time,
                reason_codes=(NoSignalReason.INSUFFICIENT_DATA,),
            )

        asia_high = max(c.high for c in asia_candles)
        asia_low = min(c.low for c in asia_candles)
        asia_range = asia_high - asia_low

        if asia_range <= 0:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time,
                latest_trend_candle_time=htf[-1].start_time,
                reason_codes=(NoSignalReason.NO_CROSSOVER,),
            )

        # Check for London manipulation on 5m candles
        london_5m = [
            c for c in entry
            if _LONDON_START_HOUR <= c.start_time.hour < _LONDON_END_HOUR
            and c.start_time.date() == (asia_candles[-1].start_time.date() if asia_candles else today)
        ]

        swept_low = False
        swept_high = False
        for c in london_5m:
            if c.low < asia_low:
                swept_low = True
            if c.high > asia_high:
                swept_high = True

        # Distribution entry: look for reversal on recent 5m candles
        side: SignalSide | None = None
        clean_sweep = False

        if swept_low and not swept_high:
            # Bearish manipulation (swept lows) → expect bullish distribution
            # Look for 5m close back above asia_low
            if entry[-1].close > asia_low:
                side = SignalSide.BUY
                sweep_depth = (asia_low - min(c.low for c in london_5m)) / asia_low if london_5m else Decimal(0)
                clean_sweep = sweep_depth > _SWEEP_MIN_PCT
        elif swept_high and not swept_low:
            # Bullish manipulation (swept highs) → expect bearish distribution
            # Look for 5m close back below asia_high
            if entry[-1].close < asia_high:
                side = SignalSide.SELL
                sweep_depth = (max(c.high for c in london_5m) - asia_high) / asia_high if london_5m else Decimal(0)
                clean_sweep = sweep_depth > _SWEEP_MIN_PCT

        if side is None:
            return StrategyEvaluation(
                symbol=symbol,
                strategy=self.name,
                evaluation_time=now,
                latest_entry_candle_time=entry[-1].start_time,
                latest_trend_candle_time=htf[-1].start_time,
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
                latest_trend_candle_time=htf[-1].start_time,
                reason_codes=(NoSignalReason.DUPLICATE_SETUP,),
            )

        # Confidence
        confidence = 80
        if clean_sweep:
            confidence += 10
        # Strong reversal candle check
        last = entry[-1]
        if side == SignalSide.BUY and last.close > last.open:
            body = last.close - last.open
            total = last.high - last.low
            if total > 0 and body / total > Decimal("0.6"):
                confidence += 10
        elif side == SignalSide.SELL and last.close < last.open:
            body = last.open - last.close
            total = last.high - last.low
            if total > 0 and body / total > Decimal("0.6"):
                confidence += 10
        confidence = min(confidence, 100)

        closes_5m = tuple(c.close for c in entry)
        volumes_5m = tuple(c.volume for c in entry)
        ema9 = ema(closes_5m, 9)
        ema21 = ema(closes_5m, 21)
        avg_vol = moving_average(volumes_5m, 20)

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
            adx=Decimal(0),
            volume=volumes_5m[-1],
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
            latest_entry_candle_time=entry[-1].start_time,
            latest_trend_candle_time=htf[-1].start_time,
            signal=signal,
        )

    @staticmethod
    def _closed(candles: tuple[Candle, ...], symbol: str, tf: str) -> tuple[Candle, ...]:
        by_time = {
            c.start_time: c for c in candles
            if c.is_closed and c.symbol == symbol and c.timeframe == tf
        }
        return tuple(sorted(by_time.values(), key=lambda c: c.start_time))
