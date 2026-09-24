"""Concrete strategy workers that wrap each strategy for the Strategy Lab."""

from app.models.candle import SupportedSymbol
from app.models.signal import StrategyEvaluation, StrategyName
from app.strategies.base_worker import BaseStrategyWorker
from app.strategies.ict import ICTStrategy
from app.strategies.smc import SMCStrategy
from app.strategies.amd import AMDStrategy
from app.strategies.liquidity_sweep import LiquiditySweepStrategy
from app.market_data.service import MarketDataService


class ICTWorker(BaseStrategyWorker):
    def __init__(self, market_data: MarketDataService) -> None:
        self._market_data = market_data
        self._strategy = ICTStrategy()

    @property
    def strategy_name(self) -> str:
        return StrategyName.ICT_STRATEGY

    async def evaluate(self, symbol: SupportedSymbol) -> StrategyEvaluation:
        entry = await self._market_data.fetch_candles(symbol, "5m", limit=100, closed_only=True)
        trend = await self._market_data.fetch_candles(symbol, "15m", limit=50, closed_only=True)
        htf = await self._market_data.fetch_candles(symbol, "1H", limit=50, closed_only=True)
        return await self._strategy.evaluate(symbol, entry, trend, htf)


class SMCWorker(BaseStrategyWorker):
    def __init__(self, market_data: MarketDataService) -> None:
        self._market_data = market_data
        self._strategy = SMCStrategy()

    @property
    def strategy_name(self) -> str:
        return StrategyName.SMC_STRATEGY

    async def evaluate(self, symbol: SupportedSymbol) -> StrategyEvaluation:
        entry = await self._market_data.fetch_candles(symbol, "5m", limit=100, closed_only=True)
        trend = await self._market_data.fetch_candles(symbol, "15m", limit=50, closed_only=True)
        return await self._strategy.evaluate(symbol, entry, trend)


class AMDWorker(BaseStrategyWorker):
    def __init__(self, market_data: MarketDataService) -> None:
        self._market_data = market_data
        self._strategy = AMDStrategy()

    @property
    def strategy_name(self) -> str:
        return StrategyName.AMD_STRATEGY

    async def evaluate(self, symbol: SupportedSymbol) -> StrategyEvaluation:
        entry = await self._market_data.fetch_candles(symbol, "5m", limit=100, closed_only=True)
        htf = await self._market_data.fetch_candles(symbol, "1H", limit=48, closed_only=True)
        return await self._strategy.evaluate(symbol, entry, htf)


class LiquiditySweepWorker(BaseStrategyWorker):
    def __init__(self, market_data: MarketDataService) -> None:
        self._market_data = market_data
        self._strategy = LiquiditySweepStrategy()

    @property
    def strategy_name(self) -> str:
        return StrategyName.LIQUIDITY_SWEEP

    async def evaluate(self, symbol: SupportedSymbol) -> StrategyEvaluation:
        fast = await self._market_data.fetch_candles(symbol, "1m", limit=100, closed_only=True)
        confirm = await self._market_data.fetch_candles(symbol, "5m", limit=50, closed_only=True)
        return await self._strategy.evaluate(symbol, fast, confirm)
