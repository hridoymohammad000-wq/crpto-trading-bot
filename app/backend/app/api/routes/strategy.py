from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request

from app.models.signal import StrategyDiagnosticResponse
from app.strategies.service import StrategyService

router = APIRouter(prefix="/strategy")


def get_strategy_service(request: Request) -> StrategyService:
    return cast(StrategyService, request.app.state.strategy_service)


@router.get("/evaluate", response_model=StrategyDiagnosticResponse)
async def evaluate_strategy(
    symbol: Annotated[str, Query(pattern=r"^[A-Z0-9]+USDT$")],
    service: StrategyService = Depends(get_strategy_service),
) -> StrategyDiagnosticResponse:
    evaluation = await service.evaluate(symbol)
    return StrategyDiagnosticResponse.from_evaluation(evaluation)
