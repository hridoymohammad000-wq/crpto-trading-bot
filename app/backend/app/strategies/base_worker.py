"""Base class for all strategy workers in Strategy Lab."""

from abc import ABC, abstractmethod

from app.models.candle import SupportedSymbol
from app.models.signal import StrategyEvaluation


class BaseStrategyWorker(ABC):
    """Contract that every Strategy Lab worker must implement."""

    @abstractmethod
    async def evaluate(self, symbol: SupportedSymbol) -> StrategyEvaluation:
        """Evaluate the strategy for a given symbol and return signal or no-signal."""
        ...

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Strategy display name."""
        ...
