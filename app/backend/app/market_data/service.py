from collections import defaultdict
from collections.abc import Iterable

from app.exchange.base import ExchangeClient
from app.exchange.bybit.client import MarketTicker, InstrumentInfo
from app.models.candle import Candle


DEFAULT_MAX_HISTORY = 500


class MarketDataService:
    def __init__(
        self,
        exchange: ExchangeClient,
        *,
        max_history: int = DEFAULT_MAX_HISTORY,
    ) -> None:
        if max_history < 1:
            raise ValueError("max_history must be at least 1")
        self._exchange = exchange
        self._max_history = max_history
        self._history: dict[tuple[str, str], list[Candle]] = defaultdict(list)

    async def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = 200,
        closed_only: bool = False,
    ) -> tuple[Candle, ...]:
        candles = await self._exchange.get_candles(symbol, timeframe, limit)
        self.merge(candles)
        history = self._history.get((symbol, timeframe), [])
        if closed_only:
            history = [candle for candle in history if candle.is_closed]
        return tuple(history[-limit:])



    async def fetch_all_tickers(self) -> tuple[MarketTicker, ...]:
        method = getattr(self._exchange, "get_all_tickers", None)
        if method is None:
            raise NotImplementedError("Exchange client does not provide bulk ticker data")
        return await method()

    async def fetch_all_instruments(self) -> tuple[InstrumentInfo, ...]:
        method = getattr(self._exchange, "get_all_instruments", None)
        if method is None:
            raise NotImplementedError("Exchange client does not provide instrument metadata")
        return await method()

    async def fetch_ticker(self, symbol: str) -> MarketTicker:
        get_ticker = getattr(self._exchange, "get_ticker", None)
        if get_ticker is None:
            raise NotImplementedError("Exchange client does not provide ticker data")
        return await get_ticker(symbol)

    def merge(self, candles: Iterable[Candle]) -> None:
        grouped: dict[tuple[str, str], list[Candle]] = defaultdict(list)
        for candle in candles:
            grouped[(candle.symbol, candle.timeframe)].append(candle)

        for key, batch in grouped.items():
            by_start_time = {
                candle.start_time: candle for candle in self._history.get(key, [])
            }
            for candle in batch:
                by_start_time[candle.start_time] = candle
            ordered = sorted(by_start_time.values(), key=lambda candle: candle.start_time)
            self._history[key] = ordered[-self._max_history :]

    def latest_closed_candle(
        self,
        symbol: str,
        timeframe: str,
    ) -> Candle | None:
        closed = self.recent_closed_candles(symbol, timeframe, limit=1)
        return closed[-1] if closed else None

    def recent_closed_candles(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = 200,
    ) -> tuple[Candle, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        history = self._history.get((symbol, timeframe), [])
        closed = [candle for candle in history if candle.is_closed]
        return tuple(closed[-limit:])
