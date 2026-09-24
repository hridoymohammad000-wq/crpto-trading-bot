from typing import Protocol

from app.models.candle import Candle, SupportedSymbol
from app.models.signal import StrategyEvaluation
from app.strategies.momentum import EmaRsiAdxMomentumStrategy


class MarketDataProvider(Protocol):
    async def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = 200,
        closed_only: bool = False,
    ) -> tuple[Candle, ...]: ...


class StrategyService:
    def __init__(
        self,
        market_data: MarketDataProvider,
        strategy: EmaRsiAdxMomentumStrategy | None = None,
    ) -> None:
        self._market_data = market_data
        self._strategy = strategy or EmaRsiAdxMomentumStrategy()

    async def evaluate(self, symbol: SupportedSymbol) -> StrategyEvaluation:
        entry = await self._market_data.fetch_candles(
            symbol, "5m", limit=200, closed_only=True
        )
        trend = await self._market_data.fetch_candles(
            symbol, "15m", limit=200, closed_only=True
        )
        return self._strategy.evaluate(symbol, entry, trend)
