from typing import Protocol

from app.core.config import settings
from app.models.candle import Candle, SupportedSymbol
from app.models.signal import StrategyEvaluation
from app.strategies.alphaflow import AlphaFlowStrategy
from app.strategies.momentum import EmaRsiAdxMomentumStrategy


class MarketDataProvider(Protocol):
    async def fetch_candles(self, symbol, timeframe, *, limit=200, closed_only=False): ...


class StrategyService:
    def __init__(self, market_data, strategy=None):
        self._market_data = market_data
        if strategy is not None:
            self._strategy = strategy
        else:
            mode = getattr(settings, "STRATEGY_MODE", "alphaflow").strip().lower()
            if mode == "momentum":
                self._strategy = EmaRsiAdxMomentumStrategy()
            else:
                self._strategy = AlphaFlowStrategy()

    async def evaluate(self, symbol, *, entry_candles=None, trend_candles=None, htf_candles=None):
        entry = entry_candles
        if entry is None:
            entry = await self._market_data.fetch_candles(symbol, "5m", limit=200, closed_only=True)
        trend = trend_candles
        if trend is None:
            trend = await self._market_data.fetch_candles(symbol, "15m", limit=200, closed_only=True)
        htf = htf_candles
        if htf is None:
            try:
                htf = await self._market_data.fetch_candles(symbol, "1H", limit=60, closed_only=True)
            except Exception:
                htf = ()
        return self._strategy.evaluate(symbol, entry, trend, htf)
