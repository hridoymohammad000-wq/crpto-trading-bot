from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.candle import Candle
from app.models.signal import StrategyEvaluation, StrategySignal
from app.scanner.models import SetupState, SymbolState
from app.strategies.indicators import adx, ema


class PipelineStateMachine:
    """Production state transitions for scanner-managed symbols."""

    @staticmethod
    def should_process(state: SymbolState, timeframe: str, candle: Candle | None) -> bool:
        if candle is None or not candle.is_closed:
            return False
        attr = {"1H": "last_processed_1h", "15m": "last_processed_15m", "5m": "last_processed_5m"}[timeframe]
        return getattr(state, attr) != candle.start_time

    @staticmethod
    def mark_processed(state: SymbolState, timeframe: str, candle: Candle) -> None:
        attr = {"1H": "last_processed_1h", "15m": "last_processed_15m", "5m": "last_processed_5m"}[timeframe]
        setattr(state, attr, candle.start_time)

    @staticmethod
    def evaluate_1h_trend(state: SymbolState, candles_1h: tuple[Candle, ...]) -> bool:
        closed = tuple(c for c in candles_1h if c.is_closed)
        if len(closed) < 22:
            state.reason_codes = ["INSUFFICIENT_1H_HISTORY"]
            return False
        latest = closed[-1]
        if not PipelineStateMachine.should_process(state, "1H", latest):
            return bool(state.trend_1h.get("trend_valid", False))

        closes = tuple(c.close for c in closed)
        fast = ema(closes, 9)[-1]
        slow = ema(closes, 21)[-1]
        PipelineStateMachine.mark_processed(state, "1H", latest)
        if fast is None or slow is None:
            state.reason_codes = ["INSUFFICIENT_1H_INDICATORS"]
            return False

        up = fast > slow and latest.close > slow
        down = fast < slow and latest.close < slow
        valid = up or down
        state.bias = "LONG" if up else "SHORT" if down else None
        state.trend_1h = {
            "ema_fast": float(fast),
            "ema_slow": float(slow),
            "trend_valid": valid,
            "trend": "TRENDING UP" if up else "TRENDING DOWN" if down else "NONE",
            "time": latest.start_time.isoformat(),
        }
        if state.state == SetupState.COOLDOWN:
            return valid
        if valid:
            if state.state in {SetupState.DISCOVERED, SetupState.INVALIDATED, SetupState.WATCHING}:
                state.state = SetupState.WATCHING
            state.reason_codes = ["HTF_VALID"]
        else:
            state.state = SetupState.INVALIDATED if state.state != SetupState.DISCOVERED else SetupState.DISCOVERED
            state.reason_codes = ["HTF_1H_FAILED"]
        return valid

    @staticmethod
    def evaluate_15m_setup(state: SymbolState, candles_15m: tuple[Candle, ...]) -> bool:
        closed = tuple(c for c in candles_15m if c.is_closed)
        if len(closed) < 22:
            state.reason_codes = ["INSUFFICIENT_15M_HISTORY"]
            return False
        latest = closed[-1]
        if not PipelineStateMachine.should_process(state, "15m", latest):
            return bool(state.setup_15m.get("setup_valid", False))

        closes = tuple(c.close for c in closed)
        highs = tuple(c.high for c in closed)
        lows = tuple(c.low for c in closed)
        fast = ema(closes, 9)[-1]
        slow = ema(closes, 21)[-1]
        adx_val = adx(highs, lows, closes, 14)[-1]
        PipelineStateMachine.mark_processed(state, "15m", latest)
        if fast is None or slow is None or adx_val is None:
            state.reason_codes = ["INSUFFICIENT_15M_INDICATORS"]
            return False

        up = fast > slow and latest.close > fast and adx_val >= Decimal("20")
        down = fast < slow and latest.close < fast and adx_val >= Decimal("20")
        valid = up or down
        state.bias = "LONG" if up else "SHORT" if down else None
        state.setup_15m = {
            "ema_fast": float(fast), "ema_slow": float(slow), "adx": float(adx_val),
            "setup_valid": valid, "trend": "UP" if up else "DOWN" if down else "NONE",
            "time": latest.start_time.isoformat(),
        }
        if state.state == SetupState.COOLDOWN:
            return valid
        if valid:
            if state.state in {SetupState.DISCOVERED, SetupState.INVALIDATED, SetupState.WATCHING}:
                state.state = SetupState.WATCHING
        else:
            state.state = SetupState.INVALIDATED if state.state != SetupState.DISCOVERED else SetupState.DISCOVERED
            state.reason_codes = ["SETUP_15M_FAILED"]
        return valid

    @staticmethod
    def evaluate_5m_entry(state: SymbolState, evaluation: StrategyEvaluation) -> bool:
        if state.state == SetupState.COOLDOWN:
            return False
        latest_time = evaluation.latest_entry_candle_time
        if latest_time is not None and state.last_processed_5m == latest_time:
            return bool(state.entry_5m.get("entry_valid", False))
        if latest_time is not None:
            state.last_processed_5m = latest_time

        indicators = evaluation.indicators
        crossover_age = evaluation.crossover_age_candles
        reasons = [r.value for r in evaluation.reason_codes]
        has_signal = evaluation.signal is not None
        state.entry_5m = {
            "ema_fast": float(indicators.ema_fast) if indicators and indicators.ema_fast is not None else None,
            "ema_slow": float(indicators.ema_slow) if indicators and indicators.ema_slow is not None else None,
            "rsi": float(indicators.rsi) if indicators and indicators.rsi is not None else None,
            "adx": float(indicators.adx) if indicators and indicators.adx is not None else None,
            "rvol": float(indicators.volume / indicators.average_volume) if indicators and indicators.volume is not None and indicators.average_volume else None,
            "crossover_age": crossover_age,
            "entry_valid": has_signal,
            "entry_window_valid": crossover_age is not None and crossover_age <= 3,
            "strategy_reasons": reasons,
            "time": evaluation.evaluation_time.isoformat(),
        }
        if state.state == SetupState.WATCHING and has_signal:
            state.state = SetupState.ARMED
            state.reason_codes = ["ENTRY_VALID"]
            state.entry_5m["signal"] = evaluation.signal
        elif state.state == SetupState.ARMED:
            if has_signal:
                state.entry_5m["signal"] = evaluation.signal
            else:
                state.state = SetupState.INVALIDATED
                state.reason_codes = ["ENTRY_WINDOW_EXPIRED"] if "ENTRY_WINDOW_EXPIRED" in reasons else ["SETUP_BROKEN"]
        elif state.state == SetupState.TRIGGERED and not has_signal:
            state.state = SetupState.INVALIDATED
            state.reason_codes = ["SETUP_BROKEN"]
        return has_signal

    @staticmethod
    def confirm_5m_entry(state: SymbolState) -> bool:
        """Use the existing approved 5m strategy signal as execution authority."""
        if state.state != SetupState.ARMED or not state.execution_allowed:
            return False
        signal = state.entry_5m.get("signal")
        if not isinstance(signal, StrategySignal):
            return False
        state.state = SetupState.TRIGGERED
        state.entry_5m.update({"entry_status": True, "entry_reason": "APPROVED_EXISTING_5M_STRATEGY_AUTHORITY"})
        state.reason_codes = ["STRATEGY_AUTHORITY_TRIGGER"]
        return True


    @staticmethod
    def mark_executed(state: SymbolState, order_id: str | None) -> None:
        state.state = SetupState.EXECUTED
        state.execution_diagnostics.update({"execution_status": "SUBMITTED", "order_id": order_id})
        state.reason_codes = ["ORDER_ACCEPTED"]

    @staticmethod
    def invalidate(state: SymbolState, reason: str) -> None:
        state.state = SetupState.INVALIDATED
        state.reason_codes = [reason]
        state.execution_diagnostics["execution_status"] = reason

    @staticmethod
    def enter_cooldown(state: SymbolState, minutes: int, *, now: datetime | None = None) -> datetime:
        now = now or datetime.now(timezone.utc)
        until = now + timedelta(minutes=minutes)
        state.state = SetupState.COOLDOWN
        state.cooldown_until = until
        state.reason_codes = ["COOLDOWN_ACTIVE"]
        return until

    @staticmethod
    def release_cooldown(state: SymbolState, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        if state.state != SetupState.COOLDOWN or state.cooldown_until is None or now < state.cooldown_until:
            return False
        state.state = SetupState.DISCOVERED
        state.cooldown_until = None
        state.reason_codes = ["COOLDOWN_EXPIRED"]
        return True
