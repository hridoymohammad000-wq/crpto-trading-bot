from abc import ABC, abstractmethod

from app.models.candle import Candle


class ExchangeClient(ABC):
    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def get_server_time(self) -> object:
        pass

    @abstractmethod
    async def get_account_balance(self) -> object:
        pass

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> tuple[Candle, ...]:
        pass

    @abstractmethod
    async def get_positions(self) -> object:
        pass

    @abstractmethod
    async def place_order(self) -> object:
        pass
