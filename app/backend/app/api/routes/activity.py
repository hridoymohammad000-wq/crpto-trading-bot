from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.activity import ActivityService
from app.exchange.bybit.exceptions import BybitAPIError, BybitAuthenticationError, BybitConnectionError
from app.models.activity import ClosedTradeResponse, SignalActivityResponse, TradeStatsResponse

router = APIRouter()


def get_activity_service(request: Request) -> ActivityService:
    return cast(ActivityService, request.app.state.activity_service)


def _translate_bybit_error(exc: Exception) -> HTTPException:
    if isinstance(exc, BybitAuthenticationError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bybit Demo API credentials are not configured")
    if isinstance(exc, BybitConnectionError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bybit Demo API is unavailable")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Bybit Demo API returned an invalid response")


@router.get("/signals", response_model=list[SignalActivityResponse])
async def get_signals(
    limit: int = Query(default=100, ge=1, le=500),
    service: ActivityService = Depends(get_activity_service),
) -> list[SignalActivityResponse]:
    return service.list_signals(limit=limit)


@router.get("/trades", response_model=list[ClosedTradeResponse])
async def get_trades(
    limit: int = Query(default=100, ge=1, le=100),
    service: ActivityService = Depends(get_activity_service),
) -> list[ClosedTradeResponse]:
    try:
        return await service.list_trades(limit=limit)
    except (BybitAuthenticationError, BybitConnectionError, BybitAPIError) as exc:
        raise _translate_bybit_error(exc) from exc


@router.get("/trades/stats", response_model=TradeStatsResponse)
async def get_trade_stats(
    limit: int = Query(default=100, ge=1, le=100),
    service: ActivityService = Depends(get_activity_service),
) -> TradeStatsResponse:
    try:
        return await service.get_trade_stats(limit=limit)
    except (BybitAuthenticationError, BybitConnectionError, BybitAPIError) as exc:
        raise _translate_bybit_error(exc) from exc

@router.get("/trades/persisted", response_model=list[ClosedTradeResponse])
def get_persisted_trades(
    limit: int = Query(default=100, ge=1, le=500),
    service: ActivityService = Depends(get_activity_service),
) -> list[ClosedTradeResponse]:
    return service.list_persisted_trades(limit=limit)


@router.get("/trades/stats/persisted", response_model=TradeStatsResponse)
def get_persisted_trade_stats(
    limit: int = Query(default=100, ge=1, le=500),
    service: ActivityService = Depends(get_activity_service),
) -> TradeStatsResponse:
    return service.get_persisted_trade_stats(limit=limit)
