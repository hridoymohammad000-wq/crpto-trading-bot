"""AlphaFlow Strategy - RELAXED version for testing."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import NAMESPACE_URL, uuid5

from app.models.candle import Candle, SupportedSymbol
from app.models.signal import (
    IndicatorSnapshot, NoSignalReason, SignalSide,
    StrategyEvaluation, StrategyName, StrategySignal,
)
from app.strategies.indicators import adx, atr, ema, moving_average, rsi

ENTRY_TIMEFRAME = "5m"
TREND_TIMEFRAME = "15m"
HTF_TIMEFRAME = "1H"
EMA_FAST = 20
EMA_SLOW = 30
ADX_THRESHOLD = Decimal("15")
VOL_MULTIPLIER = Decimal("0.8")
BODY_RATIO_MIN = Decimal("0.25")


class AlphaFlowStrategy:
    name = StrategyName.ALPHAFLOW

    def __init__(self):
        self._emitted_setups = set()

    def reset(self):
        self._emitted_setups.clear()

    def evaluate(self, symbol, entry_candles, trend_candles, htf_candles=None):
        entry = self._closed_for(entry_candles, symbol, ENTRY_TIMEFRAME)
        trend = self._closed_for(trend_candles, symbol, TREND_TIMEFRAME)
        htf = self._closed_for(htf_candles or (), symbol, HTF_TIMEFRAME)
        et = self._evaluation_time(entry, trend, htf)

        if len(htf) < 35 or len(trend) < 22:
            return self._no_signal(symbol, et, entry, trend, NoSignalReason.INSUFFICIENT_DATA)

        htf_closes = tuple(c.close for c in htf)
        htf_highs = tuple(c.high for c in htf)
        htf_lows = tuple(c.low for c in htf)
        htf_ema20 = ema(htf_closes, EMA_FAST)[-1]
        htf_ema30 = ema(htf_closes, EMA_SLOW)[-1]
        htf_adx_raw = adx(htf_highs, htf_lows, htf_closes, 14)
        htf_adx = htf_adx_raw[-1] if htf_adx_raw else None

        if htf_ema20 is None or htf_ema30 is None:
            return self._no_signal(symbol, et, entry, trend, NoSignalReason.INSUFFICIENT_DATA)

        price = htf_closes[-1]
        adx_val = htf_adx if htf_adx is not None else Decimal(0)

        long_trend = htf_ema20 > htf_ema30 and price > htf_ema30
        short_trend = htf_ema20 < htf_ema30 and price < htf_ema30

        if not long_trend and not short_trend:
            return self._no_signal(symbol, et, entry, trend, NoSignalReason.HTF_TREND_FAILED)
        side = SignalSide.BUY if long_trend else SignalSide.SELL

        if len(trend) < 4:
            return self._no_signal(symbol, et, entry, trend, NoSignalReason.INSUFFICIENT_DATA)

        curr_15m = trend[-2]
        body = abs(curr_15m.close - curr_15m.open)
        total_range = curr_15m.high - curr_15m.low
        body_ratio = (body / total_range) if total_range > 0 else Decimal(0)

        if side == SignalSide.BUY:
            directional = curr_15m.close > curr_15m.open
        else:
            directional = curr_15m.close < curr_15m.open

        if not directional or body_ratio < BODY_RATIO_MIN:
            return self._no_signal(symbol, et, entry, trend, NoSignalReason.CANDLE_CONFIRMATION_FAILED)

        vol_sma_series = moving_average(tuple(c.volume for c in trend[:-1]), 3)
        vol_sma = vol_sma_series[-1] if vol_sma_series else None
        if vol_sma is None:
            return self._no_signal(symbol, et, entry, trend, NoSignalReason.INSUFFICIENT_DATA)

        if curr_15m.volume < (vol_sma * VOL_MULTIPLIER):
            return self._no_signal(symbol, et, entry, trend, NoSignalReason.VOLUME_FILTER_FAILED)

        tc = tuple(c.close for c in trend)
        th = tuple(c.high for c in trend)
        tl = tuple(c.low for c in trend)
        ema20_15 = ema(tc, EMA_FAST)[-1]
        ema30_15 = ema(tc, EMA_SLOW)[-1]
        rsi_15 = rsi(tc, 14)[-1]
        adx_15_raw = adx(th, tl, tc, 14)
        adx_15 = adx_15_raw[-1] if adx_15_raw else Decimal(0)
        atr_raw = atr(th, tl, tc, 14)
        atr_15 = atr_raw[-1] if atr_raw else None
        avg_vol_series = moving_average(tuple(c.volume for c in trend), 20)
        avg_vol_15 = avg_vol_series[-1] if avg_vol_series else None

        if any(v is None for v in (ema20_15, ema30_15, rsi_15, atr_15, avg_vol_15)):
            return self._no_signal(symbol, et, entry, trend, NoSignalReason.INSUFFICIENT_DATA)

        htf_ema20_series = ema(htf_closes, EMA_FAST)
        htf_ema20_prev = htf_ema20_series[-2] if len(htf_ema20_series) > 1 else htf_ema20
        if htf_ema20_prev is None:
            htf_ema20_prev = htf_ema20

        signal_time = curr_15m.start_time + timedelta(minutes=15)
        setup_key = (symbol, self.name, signal_time, side)
        if setup_key in self._emitted_setups:
            return self._no_signal(symbol, et, entry, trend, NoSignalReason.DUPLICATE_SETUP)

        confidence = self._confidence(adx_val, curr_15m.volume, vol_sma)

        signal = StrategySignal(
            signal_id=str(uuid5(NAMESPACE_URL, ":".join(map(str, setup_key)))),
            symbol=symbol,
            strategy=self.name,
            side=side,
            entry_timeframe=TREND_TIMEFRAME,
            trend_timeframe=HTF_TIMEFRAME,
            signal_time=signal_time,
            reference_entry_price=curr_15m.close,
            ema_fast=ema20_15,
            ema_slow=ema30_15,
            rsi=rsi_15,
            adx=adx_15,
            volume=curr_15m.volume,
            average_volume=avg_vol_15,
            higher_tf_ema_fast=htf_ema20,
            higher_tf_ema_slow=htf_ema30,
            higher_tf_ema_fast_previous=htf_ema20_prev,
            crossover_age_candles=0,
            confidence=confidence,
            atr=atr_15,
        )
        self._emitted_setups.add(setup_key)

        return StrategyEvaluation(
            symbol=symbol,
            strategy=self.name,
            evaluation_time=et,
            latest_entry_candle_time=curr_15m.start_time,
            latest_trend_candle_time=trend[-1].start_time,
            signal=signal,
            reason_codes=(),
            indicators=IndicatorSnapshot(
                ema_fast=ema20_15,
                ema_slow=ema30_15,
                rsi=rsi_15,
                adx=adx_15,
                atr=atr_15,
                volume=curr_15m.volume,
                average_volume=avg_vol_15,
                higher_tf_ema_fast=htf_ema20,
                higher_tf_ema_slow=htf_ema30,
                higher_tf_ema_fast_previous=htf_ema20_prev,
            ),
            crossover_age_candles=0,
        )

    @staticmethod
    def _confidence(adx_val, volume, avg_volume):
        adx_score = min(Decimal(40), max(Decimal(0), adx_val))
        if avg_volume and avg_volume > 0:
            vol_bonus = min(Decimal(30), (Decimal(volume) / Decimal(avg_volume)) * Decimal(15))
        else:
            vol_bonus = Decimal(0)
        base = Decimal(30) + adx_score + vol_bonus
        return int(min(Decimal(100), base).quantize(Decimal(1), rounding=ROUND_HALF_UP))

    @staticmethod
    def _closed_for(candles, symbol, timeframe):
        d = {c.start_time: c for c in candles if c.is_closed and c.symbol == symbol and c.timeframe == timeframe}
        return tuple(sorted(d.values(), key=lambda x: x.start_time))

    @staticmethod
    def _evaluation_time(entry, trend, htf):
        times = []
        if entry: times.append(entry[-1].start_time + timedelta(minutes=5))
        if trend: times.append(trend[-1].start_time + timedelta(minutes=15))
        if htf: times.append(htf[-1].start_time + timedelta(hours=1))
        return max(times) if times else datetime.now(timezone.utc)

    def _no_signal(self, symbol, et, entry, trend, reason):
        return StrategyEvaluation(
            symbol=symbol,
            strategy=self.name,
            evaluation_time=et,
            latest_entry_candle_time=entry[-1].start_time if entry else None,
            latest_trend_candle_time=trend[-1].start_time if trend else None,
            reason_codes=(reason,),
        )
