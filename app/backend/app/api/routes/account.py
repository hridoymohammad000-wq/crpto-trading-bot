from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.account import AccountService
from app.exchange.bybit.exceptions import (
    BybitAPIError,
    BybitAuthenticationError,
    BybitConnectionError,
)
from app.models.account import AccountSummaryResponse, PositionResponse

router = APIRouter()


def get_account_service(request: Request) -> AccountService:
    return cast(AccountService, request.app.state.account_service)


def _translate_bybit_error(exc: Exception) -> HTTPException:
    if isinstance(exc, BybitAuthenticationError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bybit Demo API credentials are not configured",
        )
    if isinstance(exc, BybitConnectionError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bybit Demo API is unavailable",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Bybit Demo API returned an invalid response",
    )


@router.get("/account", response_model=AccountSummaryResponse)
async def get_account(
    service: AccountService = Depends(get_account_service),
) -> AccountSummaryResponse:
    try:
        return await service.get_summary()
    except (BybitAuthenticationError, BybitConnectionError, BybitAPIError) as exc:
        raise _translate_bybit_error(exc) from exc


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(
    service: AccountService = Depends(get_account_service),
) -> list[PositionResponse]:
    try:
        return await service.get_positions()
    except (BybitAuthenticationError, BybitConnectionError, BybitAPIError) as exc:
        raise _translate_bybit_error(exc) from exc

@router.get("/account/reconciliation")
async def get_reconciliation(request: Request):
    reconciliation_engine = getattr(request.app.state, "reconciliation_engine", None)
    if not reconciliation_engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reconciliation Engine is not available",
        )
    result = await reconciliation_engine.get_latest_result()
    return result.model_dump(mode="json")
