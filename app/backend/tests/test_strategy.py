import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes.strategy import get_strategy_service
from app.main import app
from app.models.candle import Candle
from app.models.signal import IndicatorSnapshot, NoSignalReason, SignalSide
from app.strategies.indicators import adx, ema, moving_average, rsi
from app.strategies.momentum import (
    ENTRY_HISTORY_REQUIRED,
    TREND_HISTORY_REQUIRED,
    EmaRsiAdxMomentumStrategy,
    StrategySnapshot,
)
from app.strategies.service import StrategyService

START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def candle(
    index: int,
    *,
    timeframe: str = "5m",
    symbol: str = "BTCUSDT",
    open_price: str = "100",
    close: str = "110",
    volume: str = "120",
    closed: bool = True,
) -> Candle:
    opening = Decimal(open_price)
    closing = Decimal(close)
    step = 5 if timeframe == "5m" else 15
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        start_time=START + timedelta(minutes=index * step),
        open=opening,
        high=max(opening, closing) + Decimal(2),
        low=min(opening, closing) - Decimal(2),
        close=closing,
        volume=Decimal(volume),
        turnover=Decimal(volume) * closing,
        is_closed=closed,
    )


def valid_snapshot(
    side: SignalSide,
    *,
    age: int = 0,
    **indicator_overrides: Decimal,
) -> StrategySnapshot:
    long = side == SignalSide.BUY
    current = candle(
        30,
        open_price="100" if long else "110",
        close="110" if long else "100",
    )
    values: dict[str, Decimal] = {
        "ema_fast": Decimal("105") if long else Decimal("105"),
        "ema_slow": Decimal("104") if long else Decimal("106"),
        "rsi": Decimal("60") if long else Decimal("40"),
        "adx": Decimal("32"),
        "volume": Decimal("120"),
        "average_volume": Decimal("100"),
        "higher_tf_ema_fast": Decimal("105") if long else Decimal("95"),
        "higher_tf_ema_slow": Decimal("100"),
        "higher_tf_ema_fast_previous": Decimal("104") if long else Decimal("96"),
    }
    values.update(indicator_overrides)
    return StrategySnapshot(
        symbol="BTCUSDT",
        current_candle=current,
        latest_trend_candle=candle(30, timeframe="15m"),
        crossover_time=current.start_time - timedelta(minutes=age * 5),
        crossover_age_candles=age,
        side=side,
        indicators=IndicatorSnapshot(**values),
    )


@pytest.mark.parametrize("side", [SignalSide.BUY, SignalSide.SELL])
@pytest.mark.parametrize("age", [0, 1])
def test_exact_and_next_candle_entry_windows_emit(side: SignalSide, age: int) -> None:
    result = EmaRsiAdxMomentumStrategy().evaluate_snapshot(valid_snapshot(side, age=age))

    assert result.signal is not None
    assert result.signal.side == side
    assert result.signal.crossover_age_candles == age
    assert result.reason_codes == ()


@pytest.mark.parametrize("side", [SignalSide.BUY, SignalSide.SELL])
def test_sixth_candle_is_expired(side: SignalSide) -> None:
    result = EmaRsiAdxMomentumStrategy().evaluate_snapshot(valid_snapshot(side, age=6))

    assert result.signal is None
    assert NoSignalReason.ENTRY_WINDOW_EXPIRED in result.reason_codes


@pytest.mark.parametrize("rsi_value", [Decimal("51.99"), Decimal("70.01")])
def test_long_rsi_outside_inclusive_range_fails(rsi_value: Decimal) -> None:
    result = EmaRsiAdxMomentumStrategy().evaluate_snapshot(
        valid_snapshot(SignalSide.BUY, rsi=rsi_value)
    )
    assert NoSignalReason.RSI_FILTER_FAILED in result.reason_codes


@pytest.mark.parametrize("rsi_value", [Decimal("29.99"), Decimal("48.01")])
def test_short_rsi_outside_inclusive_range_fails(rsi_value: Decimal) -> None:
    result = EmaRsiAdxMomentumStrategy().evaluate_snapshot(
        valid_snapshot(SignalSide.SELL, rsi=rsi_value)
    )
    assert NoSignalReason.RSI_FILTER_FAILED in result.reason_codes


@pytest.mark.parametrize("side", [SignalSide.BUY, SignalSide.SELL])
@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("adx", Decimal("22"), NoSignalReason.ADX_FILTER_FAILED),
        ("volume", Decimal("100"), NoSignalReason.VOLUME_FILTER_FAILED),
    ],
)
def test_common_mandatory_filters(
    side: SignalSide, field: str, value: Decimal, reason: NoSignalReason
) -> None:
    result = EmaRsiAdxMomentumStrategy().evaluate_snapshot(
        valid_snapshot(side, **{field: value})
    )
    assert reason in result.reason_codes





@pytest.mark.parametrize("side", [SignalSide.BUY, SignalSide.SELL])
def test_invalid_higher_timeframe_alignment_fails(side: SignalSide) -> None:
    overrides = (
        {"higher_tf_ema_fast": Decimal("99")}
        if side == SignalSide.BUY
        else {"higher_tf_ema_fast": Decimal("101")}
    )
    result = EmaRsiAdxMomentumStrategy().evaluate_snapshot(
        valid_snapshot(side, **overrides)
    )
    assert NoSignalReason.HTF_TREND_FAILED in result.reason_codes


@pytest.mark.parametrize("side", [SignalSide.BUY, SignalSide.SELL])
def test_invalid_higher_timeframe_slope_fails(side: SignalSide) -> None:
    overrides = (
        {"higher_tf_ema_fast_previous": Decimal("105")}
        if side == SignalSide.BUY
        else {"higher_tf_ema_fast_previous": Decimal("95")}
    )
    result = EmaRsiAdxMomentumStrategy().evaluate_snapshot(
        valid_snapshot(side, **overrides)
    )
    assert NoSignalReason.HTF_SLOPE_FAILED in result.reason_codes


def test_rsi_boundary_values_are_inclusive() -> None:
    for side, values in (
        (SignalSide.BUY, (Decimal("52"), Decimal("70"))),
        (SignalSide.SELL, (Decimal("30"), Decimal("48"))),
    ):
        for value in values:
            result = EmaRsiAdxMomentumStrategy().evaluate_snapshot(
                valid_snapshot(side, rsi=value)
            )
            assert result.signal is not None


def test_insufficient_history_returns_clean_reason() -> None:
    strategy = EmaRsiAdxMomentumStrategy()
    entry = tuple(candle(index) for index in range(ENTRY_HISTORY_REQUIRED - 1))
    trend = tuple(
        candle(index, timeframe="15m") for index in range(TREND_HISTORY_REQUIRED)
    )
    result = strategy.evaluate("BTCUSDT", entry, trend)
    assert result.signal is None
    assert result.reason_codes == (NoSignalReason.INSUFFICIENT_DATA,)


def test_unfinished_candles_are_ignored() -> None:
    entry = tuple(candle(index) for index in range(ENTRY_HISTORY_REQUIRED - 1)) + (
        candle(100, close="999", closed=False),
    )
    trend = tuple(
        candle(index, timeframe="15m") for index in range(TREND_HISTORY_REQUIRED)
    )
    result = EmaRsiAdxMomentumStrategy().evaluate("BTCUSDT", entry, trend)
    assert result.reason_codes == (NoSignalReason.INSUFFICIENT_DATA,)
    assert result.latest_entry_candle_time == entry[-2].start_time





def test_duplicate_setup_emits_only_once() -> None:
    strategy = EmaRsiAdxMomentumStrategy()
    snapshot = valid_snapshot(SignalSide.BUY)
    first = strategy.evaluate_snapshot(snapshot)
    second = strategy.evaluate_snapshot(snapshot)
    assert first.signal is not None
    assert second.signal is None
    assert second.reason_codes == (NoSignalReason.DUPLICATE_SETUP,)


def test_confidence_and_signal_id_are_deterministic() -> None:
    snapshot = valid_snapshot(SignalSide.BUY)
    first = EmaRsiAdxMomentumStrategy().evaluate_snapshot(snapshot)
    second = EmaRsiAdxMomentumStrategy().evaluate_snapshot(snapshot)
    assert first.signal is not None and second.signal is not None
    assert first.signal.confidence == second.signal.confidence == 97
    assert first.signal.signal_id == second.signal.signal_id


def test_signal_is_immutable() -> None:
    result = EmaRsiAdxMomentumStrategy().evaluate_snapshot(valid_snapshot(SignalSide.BUY))
    assert result.signal is not None
    with pytest.raises(ValidationError):
        result.signal.confidence = 0


def test_indicator_calculations_do_not_look_ahead() -> None:
    original = tuple(Decimal(index) for index in range(1, 31))
    extended = original + (Decimal("1000"),)
    assert ema(original, 9) == ema(extended, 9)[:-1]
    assert rsi(original) == rsi(extended)[:-1]
    assert moving_average(original, 20) == moving_average(extended, 20)[:-1]
    highs = tuple(value + 1 for value in original)
    lows = tuple(value - 1 for value in original)
    extended_highs = highs + (Decimal("1001"),)
    extended_lows = lows + (Decimal("999"),)
    assert adx(highs, lows, original) == adx(extended_highs, extended_lows, extended)[:-1]


def test_indicator_minimum_history_is_explicit() -> None:
    values = tuple(Decimal(index) for index in range(ENTRY_HISTORY_REQUIRED))
    result = adx(values, values, values)
    assert result[-2] is None
    assert result[-1] is not None


class FakeMarketData:
    def __init__(self, entry: tuple[Candle, ...], trend: tuple[Candle, ...]) -> None:
        self.entry = entry
        self.trend = trend
        self.calls: list[tuple[str, str, int, bool]] = []

    async def fetch_candles(
        self, symbol: str, timeframe: str, *, limit: int = 200, closed_only: bool = False
    ) -> tuple[Candle, ...]:
        self.calls.append((symbol, timeframe, limit, closed_only))
        return self.entry if timeframe == "5m" else self.trend


def test_strategy_service_uses_market_data_abstraction_and_closed_only() -> None:
    provider = FakeMarketData((), ())
    result = asyncio.run(StrategyService(provider).evaluate("BTCUSDT"))
    assert result.reason_codes == (NoSignalReason.INSUFFICIENT_DATA,)
    assert provider.calls == [
        ("BTCUSDT", "5m", 200, True),
        ("BTCUSDT", "15m", 200, True),
    ]


class FakeStrategyService:
    async def evaluate(self, symbol: str):
        return EmaRsiAdxMomentumStrategy().evaluate(symbol, (), ())


def test_diagnostic_endpoint_returns_structured_no_signal() -> None:
    app.dependency_overrides[get_strategy_service] = lambda: FakeStrategyService()
    try:
        response = TestClient(app).get(
            "/strategy/evaluate", params={"symbol": "BTCUSDT"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "symbol",
        "strategy",
        "evaluation_time",
        "latest_5m_candle_time",
        "latest_15m_candle_time",
        "result",
        "side",
        "reference_entry_price",
        "confidence",
        "reason_codes",
        "indicators",
        "crossover_age_candles",
        "duplicate_setup",
    }
    assert body["result"] == "NO_SIGNAL"
    assert body["side"] is None
    assert body["confidence"] is None
    assert body["reason_codes"] == ["INSUFFICIENT_DATA"]
    assert body["duplicate_setup"] is False
    assert all(value is None for value in body["indicators"].values())


class SignalStrategyService:
    async def evaluate(self, symbol: str):
        return EmaRsiAdxMomentumStrategy().evaluate_snapshot(
            valid_snapshot(SignalSide.BUY)
        )


def test_diagnostic_endpoint_serializes_signal_result() -> None:
    app.dependency_overrides[get_strategy_service] = lambda: SignalStrategyService()
    try:
        response = TestClient(app).get(
            "/strategy/evaluate", params={"symbol": "BTCUSDT"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "SIGNAL"
    assert body["side"] == "BUY"
    assert body["reference_entry_price"] == "110"
    assert body["confidence"] == 97
    assert body["reason_codes"] == []
    assert body["crossover_age_candles"] == 0
    assert body["duplicate_setup"] is False
    assert body["indicators"]["rsi"] == "60"


class DuplicateStrategyService:
    async def evaluate(self, symbol: str):
        strategy = EmaRsiAdxMomentumStrategy()
        snapshot = valid_snapshot(SignalSide.BUY)
        strategy.evaluate_snapshot(snapshot)
        return strategy.evaluate_snapshot(snapshot)


def test_diagnostic_endpoint_serializes_duplicate_reason() -> None:
    app.dependency_overrides[get_strategy_service] = lambda: DuplicateStrategyService()
    try:
        response = TestClient(app).get(
            "/strategy/evaluate", params={"symbol": "BTCUSDT"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "NO_SIGNAL"
    assert body["reason_codes"] == ["DUPLICATE_SETUP"]
    assert body["duplicate_setup"] is True
    assert body["crossover_age_candles"] == 0


def test_diagnostic_endpoint_rejects_unsupported_symbol() -> None:
    response = TestClient(app).get(
        "/strategy/evaluate", params={"symbol": "BTCUSD"}
    )
    assert response.status_code == 422
