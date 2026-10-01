import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock

from app.models.activity import ClosedTradeResponse
from app.activity.service import ActivityService
from app.models.candle import Candle


def test_long_mae_mfe_calculation():
    now = datetime.now(timezone.utc)
    trade = ClosedTradeResponse(
        symbol="BTCUSDT",
        side="LONG",
        quantity=Decimal("1.0"),
        entry_price=Decimal("1000"),
        exit_price=Decimal("1100"),
        realized_pnl=Decimal("100"),
        created_at=now,
        updated_at=now + timedelta(minutes=30),
    )

    candles = [
        Candle(symbol="BTCUSDT", timeframe="5m", start_time=now + timedelta(minutes=5),
               open=Decimal("1000"), high=Decimal("1050"), low=Decimal("950"), close=Decimal("1020"),
               volume=Decimal("1"), turnover=Decimal("1"), is_closed=True),
        Candle(symbol="BTCUSDT", timeframe="5m", start_time=now + timedelta(minutes=10),
               open=Decimal("1020"), high=Decimal("1120"), low=Decimal("1010"), close=Decimal("1100"),
               volume=Decimal("1"), turnover=Decimal("1"), is_closed=True)
    ]
    
    # We should also add before candles for ATR
    metrics = ActivityService._trade_path_metrics(trade, candles)
    
    assert metrics["excursion_status"] == "PARTIAL" # Because earliest is now + 5m
    assert metrics["mfe_price"] == Decimal("120") # 1120 - 1000
    assert metrics["mae_price"] == Decimal("-50") # 950 - 1000
    assert metrics["mfe_r"] is None
    assert metrics["mae_r"] is None

def test_short_mae_mfe_calculation():
    now = datetime.now(timezone.utc)
    trade = ClosedTradeResponse(
        symbol="BTCUSDT",
        side="SHORT",
        quantity=Decimal("1.0"),
        entry_price=Decimal("1000"),
        exit_price=Decimal("900"),
        realized_pnl=Decimal("100"),
        created_at=now,
        updated_at=now + timedelta(minutes=30),
    )

    candles = [
        Candle(symbol="BTCUSDT", timeframe="5m", start_time=now,
               open=Decimal("1000"), high=Decimal("1050"), low=Decimal("950"), close=Decimal("1020"),
               volume=Decimal("1"), turnover=Decimal("1"), is_closed=True),
        Candle(symbol="BTCUSDT", timeframe="5m", start_time=now + timedelta(minutes=5),
               open=Decimal("1020"), high=Decimal("1120"), low=Decimal("800"), close=Decimal("900"),
               volume=Decimal("1"), turnover=Decimal("1"), is_closed=True)
    ]
    
    metrics = ActivityService._trade_path_metrics(trade, candles)
    
    assert metrics["excursion_status"] == "COMPLETE"
    assert metrics["mfe_price"] == Decimal("200") # 1000 - 800
    assert metrics["mae_price"] == Decimal("-120") # 1000 - 1120

def test_r_calculation_and_stop_too_tight():
    now = datetime.now(timezone.utc)
    trade = ClosedTradeResponse(
        symbol="BTCUSDT",
        side="LONG",
        quantity=Decimal("1.0"),
        entry_price=Decimal("1000"),
        exit_price=Decimal("900"),
        stop_loss=Decimal("900"),
        realized_pnl=Decimal("-100"),
        created_at=now,
        updated_at=now + timedelta(minutes=10),
    )

    candles = [
        Candle(symbol="BTCUSDT", timeframe="5m", start_time=now,
               open=Decimal("1000"), high=Decimal("1100"), low=Decimal("900"), close=Decimal("900"),
               volume=Decimal("1"), turnover=Decimal("1"), is_closed=True),
    ]
    
    for i in range(15):
        candles.append(Candle(symbol="BTCUSDT", timeframe="5m", start_time=now - timedelta(minutes=(i+1)*5),
               open=Decimal("1000"), high=Decimal("1100"), low=Decimal("900"), close=Decimal("1000"),
               volume=Decimal("1"), turnover=Decimal("1"), is_closed=True))

    metrics = ActivityService._trade_path_metrics(trade, candles)
    
    assert metrics["excursion_status"] == "COMPLETE"
    assert metrics["sl_distance"] == Decimal("100")
    # MFE = +100, MAE = -100, risk = 100
    assert metrics["mfe_r"] == Decimal("1.0")
    assert metrics["mae_r"] == Decimal("-1.0")

def test_no_candles():
    now = datetime.now(timezone.utc)
    trade = ClosedTradeResponse(
        symbol="BTCUSDT",
        side="LONG",
        quantity=Decimal("1.0"),
        entry_price=Decimal("1000"),
        exit_price=Decimal("900"),
        realized_pnl=Decimal("-100"),
        created_at=now,
        updated_at=now + timedelta(minutes=10),
    )
    
    metrics = ActivityService._trade_path_metrics(trade, [])
    assert metrics["excursion_status"] == "HISTORICAL_DATA_UNAVAILABLE"
    assert "mae_price" not in metrics
