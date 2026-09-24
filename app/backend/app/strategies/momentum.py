"""Pure EMA/RSI/ADX momentum strategy.

History requirements are 28 closed 5m candles (ADX14 is the limiting indicator)
and 22 closed 15m candles (current and previous seeded EMA21 values). Average
volume is the simple trailing average of the current candle and prior 19 candles.

Confidence is rounded half-up to an integer and is calculated only after every
mandatory rule passes:

* crossover freshness: 25 points at age 0, 20 at age 1
* RSI filter: 15 points
* ADX: 10 + min(10, ADX - 22), maximum 20 points
* volume: 10 + min(5, (volume / average_volume - 1) * 10), maximum 15
* higher-timeframe EMA alignment: 15 points
* higher-timeframe EMA9 slope: 10 points

Thus a valid signal scores from 80 to 100. Confidence never overrides a rule.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
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
from app.strategies.indicators import adx, ema, moving_average, rsi

ENTRY_TIMEFRAME = "5m"
TREND_TIMEFRAME = "15m"
ENTRY_HISTORY_REQUIRED = 28
TREND_HISTORY_REQUIRED = 22


@dataclass(frozen=True)
class StrategySnapshot:
    symbol: SupportedSymbol
    current_candle: Candle
    latest_trend_candle: Candle
    crossover_time: datetime
    crossover_age_candles: int
    side: SignalSide
    indicators: IndicatorSnapshot


class EmaRsiAdxMomentumStrategy:
    name = StrategyName.EMA_RSI_ADX_MOMENTUM

    def __init__(self) -> None:
        self._emitted_setups: set[
            tuple[str, StrategyName, datetime, SignalSide]
        ] = set()

    def reset(self) -> None:
        """Clear in-memory duplicate tracking (primarily useful for test isolation)."""
        self._emitted_setups.clear()

    def evaluate(
        self,
        symbol: SupportedSymbol,
        entry_candles: tuple[Candle, ...],
        trend_candles: tuple[Candle, ...],
    ) -> StrategyEvaluation:
        entry = self._closed_for(entry_candles, symbol, ENTRY_TIMEFRAME)
        trend = self._closed_for(trend_candles, symbol, TREND_TIMEFRAME)
        evaluation_time = self._evaluation_time(entry, trend)
        if len(entry) < ENTRY_HISTORY_REQUIRED or len(trend) < TREND_HISTORY_REQUIRED:
            return StrategyEvaluation(
                symbol=symbol,
                evaluation_time=evaluation_time,
                latest_entry_candle_time=entry[-1].start_time if entry else None,
                latest_trend_candle_time=trend[-1].start_time if trend else None,
                reason_codes=(NoSignalReason.INSUFFICIENT_DATA,),
            )

        snapshot = self._build_snapshot(symbol, entry, trend)
        if snapshot is None:
            indicators = self._current_indicators(entry, trend)
            latest_cross = self._latest_crossover(entry)
            reason = (
                NoSignalReason.NO_CROSSOVER
                if latest_cross is None
                else NoSignalReason.ENTRY_WINDOW_EXPIRED
            )
            return StrategyEvaluation(
                symbol=symbol,
                evaluation_time=evaluation_time,
                latest_entry_candle_time=entry[-1].start_time,
                latest_trend_candle_time=trend[-1].start_time,
                reason_codes=(reason,),
                indicators=indicators,
                crossover_age_candles=(
                    None
                    if latest_cross is None
                    else len(entry) - 1 - latest_cross[0]
                ),
            )
        return self.evaluate_snapshot(snapshot)

    def evaluate_snapshot(self, snapshot: StrategySnapshot) -> StrategyEvaluation:
        """Evaluate a fully calculated snapshot; useful for deterministic rule tests."""
        indicators = snapshot.indicators
        values = (
            indicators.ema_fast,
            indicators.ema_slow,
            indicators.rsi,
            indicators.adx,
            indicators.volume,
            indicators.average_volume,
            indicators.higher_tf_ema_fast,
            indicators.higher_tf_ema_slow,
            indicators.higher_tf_ema_fast_previous,
        )
        if any(value is None for value in values):
            return self._snapshot_result(snapshot, (NoSignalReason.INSUFFICIENT_DATA,))

        ema_fast, ema_slow, rsi_value, adx_value, volume, average_volume, htf_fast, htf_slow, htf_previous = values
        assert all(value is not None for value in values)
        reasons: list[NoSignalReason] = []
        if snapshot.crossover_age_candles > 5:
            reasons.append(NoSignalReason.ENTRY_WINDOW_EXPIRED)

        if snapshot.side == SignalSide.BUY:
            if not Decimal(52) <= rsi_value <= Decimal(70):
                reasons.append(NoSignalReason.RSI_FILTER_FAILED)
            if not htf_fast > htf_slow:
                reasons.append(NoSignalReason.HTF_TREND_FAILED)
            if not htf_fast > htf_previous:
                reasons.append(NoSignalReason.HTF_SLOPE_FAILED)
        else:
            if not Decimal(30) <= rsi_value <= Decimal(48):
                reasons.append(NoSignalReason.RSI_FILTER_FAILED)
            if not htf_fast < htf_slow:
                reasons.append(NoSignalReason.HTF_TREND_FAILED)
            if not htf_fast < htf_previous:
                reasons.append(NoSignalReason.HTF_SLOPE_FAILED)

        if not adx_value > Decimal(22):
            reasons.append(NoSignalReason.ADX_FILTER_FAILED)
        if not volume > average_volume:
            reasons.append(NoSignalReason.VOLUME_FILTER_FAILED)
        if reasons:
            return self._snapshot_result(snapshot, tuple(reasons))

        setup_key = (snapshot.symbol, self.name, snapshot.crossover_time, snapshot.side)
        if setup_key in self._emitted_setups:
            return self._snapshot_result(snapshot, (NoSignalReason.DUPLICATE_SETUP,))

        confidence = self._confidence(snapshot.crossover_age_candles, adx_value, volume, average_volume)
        signal_time = snapshot.current_candle.start_time + timedelta(minutes=5)
        signal = StrategySignal(
            signal_id=str(uuid5(NAMESPACE_URL, ":".join(map(str, setup_key)))),
            symbol=snapshot.symbol,
            strategy=self.name,
            side=snapshot.side,
            entry_timeframe=ENTRY_TIMEFRAME,
            trend_timeframe=TREND_TIMEFRAME,
            signal_time=signal_time,
            reference_entry_price=snapshot.current_candle.close,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi_value,
            adx=adx_value,
            volume=volume,
            average_volume=average_volume,
            higher_tf_ema_fast=htf_fast,
            higher_tf_ema_slow=htf_slow,
            higher_tf_ema_fast_previous=htf_previous,
            crossover_age_candles=snapshot.crossover_age_candles,
            confidence=confidence,
        )
        self._emitted_setups.add(setup_key)
        return self._snapshot_result(snapshot, (), signal)

    def _build_snapshot(
        self,
        symbol: SupportedSymbol,
        entry: tuple[Candle, ...],
        trend: tuple[Candle, ...],
    ) -> StrategySnapshot | None:
        latest_cross = self._latest_crossover(entry)
        if latest_cross is None:
            return None
        cross_index, side = latest_cross
        age = len(entry) - 1 - cross_index
        if age > 5:
            return None
            
        # Check trend structure
        if side == SignalSide.BUY and not EmaRsiAdxMomentumStrategy._has_bullish_structure(entry):
            return None
        if side == SignalSide.SELL and not EmaRsiAdxMomentumStrategy._has_bearish_structure(entry):
            return None
            
        return StrategySnapshot(
            symbol=symbol,
            current_candle=entry[-1],
            latest_trend_candle=trend[-1],
            crossover_time=entry[cross_index].start_time,
            crossover_age_candles=age,
            side=side,
            indicators=self._current_indicators(entry, trend),
        )

    @staticmethod
    def _has_bullish_structure(entry: tuple[Candle, ...], lookback: int = 6) -> bool:
        """Check for HH/HL pattern in last N candles."""
        if len(entry) < lookback:
            return False
        recent = entry[-lookback:]
        highs = [c.high for c in recent]
        lows = [c.low for c in recent]
        # At least one HH and one HL in the recent candles
        hh = any(highs[i] > highs[i-1] for i in range(1, len(highs)))
        hl = any(lows[i] > lows[i-1] for i in range(1, len(lows)))
        return hh and hl

    @staticmethod
    def _has_bearish_structure(entry: tuple[Candle, ...], lookback: int = 6) -> bool:
        """Check for LL/LH pattern in last N candles."""
        if len(entry) < lookback:
            return False
        recent = entry[-lookback:]
        highs = [c.high for c in recent]
        lows = [c.low for c in recent]
        # At least one LL and one LH in the recent candles
        ll = any(lows[i] < lows[i-1] for i in range(1, len(lows)))
        lh = any(highs[i] < highs[i-1] for i in range(1, len(highs)))
        return ll and lh

    @staticmethod
    def _closed_for(
        candles: tuple[Candle, ...], symbol: str, timeframe: str
    ) -> tuple[Candle, ...]:
        by_time = {
            candle.start_time: candle
            for candle in candles
            if candle.is_closed and candle.symbol == symbol and candle.timeframe == timeframe
        }
        return tuple(sorted(by_time.values(), key=lambda candle: candle.start_time))

    @staticmethod
    def _current_indicators(
        entry: tuple[Candle, ...], trend: tuple[Candle, ...]
    ) -> IndicatorSnapshot:
        closes = tuple(candle.close for candle in entry)
        highs = tuple(candle.high for candle in entry)
        lows = tuple(candle.low for candle in entry)
        volumes = tuple(candle.volume for candle in entry)
        trend_closes = tuple(candle.close for candle in trend)
        fast = ema(closes, 9)
        slow = ema(closes, 21)
        rsi_values = rsi(closes, 14)
        adx_values = adx(highs, lows, closes, 14)
        average_volumes = moving_average(volumes, 20)
        trend_fast = ema(trend_closes, 9)
        trend_slow = ema(trend_closes, 21)
        return IndicatorSnapshot(
            ema_fast=fast[-1],
            ema_slow=slow[-1],
            rsi=rsi_values[-1],
            adx=adx_values[-1],
            volume=volumes[-1],
            average_volume=average_volumes[-1],
            higher_tf_ema_fast=trend_fast[-1],
            higher_tf_ema_slow=trend_slow[-1],
            higher_tf_ema_fast_previous=trend_fast[-2],
        )

    @staticmethod
    def _latest_crossover(entry: tuple[Candle, ...]) -> tuple[int, SignalSide] | None:
        closes = tuple(candle.close for candle in entry)
        fast = ema(closes, 9)
        slow = ema(closes, 21)
        for index in range(len(entry) - 1, 20, -1):
            previous_fast = fast[index - 1]
            previous_slow = slow[index - 1]
            current_fast = fast[index]
            current_slow = slow[index]
            if None in (previous_fast, previous_slow, current_fast, current_slow):
                continue
            assert previous_fast is not None and previous_slow is not None
            assert current_fast is not None and current_slow is not None
            if previous_fast <= previous_slow and current_fast > current_slow:
                return index, SignalSide.BUY
            if previous_fast >= previous_slow and current_fast < current_slow:
                return index, SignalSide.SELL
        return None

    @staticmethod
    def _confidence(
        age: int, adx_value: Decimal, volume: Decimal, average_volume: Decimal
    ) -> int:
        freshness = Decimal(25 if age == 0 else 20)
        adx_score = Decimal(10) + min(Decimal(10), max(Decimal(0), adx_value - Decimal(22)))
        volume_bonus = max(Decimal(0), (volume / average_volume - Decimal(1)) * Decimal(10))
        volume_score = Decimal(10) + min(Decimal(5), volume_bonus)
        score = freshness + Decimal(15) + adx_score + volume_score + Decimal(15) + Decimal(10)
        return int(score.quantize(Decimal(1), rounding=ROUND_HALF_UP))

    @staticmethod
    def _evaluation_time(entry: tuple[Candle, ...], trend: tuple[Candle, ...]):
        times = []
        if entry:
            times.append(entry[-1].start_time + timedelta(minutes=5))
        if trend:
            times.append(trend[-1].start_time + timedelta(minutes=15))
        return max(times) if times else datetime.now(timezone.utc)

    @staticmethod
    def _snapshot_result(
        snapshot: StrategySnapshot,
        reasons: tuple[NoSignalReason, ...],
        signal: StrategySignal | None = None,
    ) -> StrategyEvaluation:
        return StrategyEvaluation(
            symbol=snapshot.symbol,
            evaluation_time=snapshot.current_candle.start_time + timedelta(minutes=5),
            latest_entry_candle_time=snapshot.current_candle.start_time,
            latest_trend_candle_time=snapshot.latest_trend_candle.start_time,
            signal=signal,
            reason_codes=reasons,
            indicators=snapshot.indicators,
            crossover_age_candles=snapshot.crossover_age_candles,
        )




