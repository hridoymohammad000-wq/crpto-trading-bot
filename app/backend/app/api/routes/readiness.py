from typing import cast

from fastapi import APIRouter, Request

from app.readiness import TradingReadinessService

router = APIRouter(prefix="/readiness")


def get_readiness_service(request: Request) -> TradingReadinessService:
    return cast(TradingReadinessService, request.app.state.trading_readiness_service)


@router.get("/last")
def last_readiness(request: Request) -> dict[str, object]:
    service = get_readiness_service(request)
    decision = service.last_decision
    if decision is None:
        return {
            "status": "BLOCKED",
            "reason_codes": ["NO_READINESS_DECISION_YET"],
        }
    return decision.model_dump(mode="json")
