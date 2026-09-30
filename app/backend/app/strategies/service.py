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

    async def evaluate(
        self,
        symbol: SupportedSymbol,
        *,
        entry_candles: tuple[Candle, ...] | None = None,
        trend_candles: tuple[Candle, ...] | None = None,
        htf_candles: tuple[Candle, ...] | None = None,
    ) -> StrategyEvaluation:
        entry = entry_candles
        if entry is None:
            entry = await self._market_data.fetch_candles(
                symbol, "5m", limit=200, closed_only=True
            )

        trend = trend_candles
        if trend is None:
            trend = await self._market_data.fetch_candles(
                symbol, "15m", limit=200, closed_only=True
            )

        htf = htf_candles
        if htf is None:
            try:
                htf = await self._market_data.fetch_candles(
                    symbol, "1H", limit=60, closed_only=True
                )
            except Exception:
                htf = ()

        return self._strategy.evaluate(symbol, entry, trend, htf)

