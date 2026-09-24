from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request

from app.market_data.service import MarketDataService
from app.models.candle import Candle, SupportedTimeframe
from app.models.market import MarketTickerResponse

router = APIRouter(prefix="/market")


def get_market_data_service(request: Request) -> MarketDataService:
    return cast(MarketDataService, request.app.state.market_data_service)


@router.get("/candles", response_model=list[Candle])
async def get_candles(
    symbol: Annotated[str, Query(pattern=r"^[A-Z0-9]+USDT$")],
    timeframe: SupportedTimeframe,
    limit: Annotated[int, Query(ge=1, le=1000)] = 20,
    service: MarketDataService = Depends(get_market_data_service),
) -> tuple[Candle, ...]:
    return await service.fetch_candles(symbol, timeframe, limit=limit)


@router.get("/ticker", response_model=MarketTickerResponse)
async def get_ticker(
    symbol: Annotated[str, Query(pattern=r"^[A-Z0-9]+USDT$")],
    service: MarketDataService = Depends(get_market_data_service),
) -> MarketTickerResponse:
    ticker = await service.fetch_ticker(symbol)
    return MarketTickerResponse(
        symbol=ticker.symbol,
        last_price=ticker.last_price,
        high_price_24h=ticker.high_price_24h,
        low_price_24h=ticker.low_price_24h,
        volume_24h=ticker.volume_24h,
        turnover_24h=ticker.turnover_24h,
        prev_price_24h=ticker.prev_price_24h,
        price_change_24h_pct=ticker.price_change_24h_pct,
        bid_price=ticker.bid_price,
        ask_price=ticker.ask_price,
    )
