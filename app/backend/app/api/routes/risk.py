from typing import cast

from fastapi import APIRouter, Request

from app.risk import RiskService

router = APIRouter(prefix="/risk")


def get_risk_service(request: Request) -> RiskService:
    return cast(RiskService, request.app.state.risk_service)


@router.get("/config")
def risk_config(request: Request) -> dict[str, object]:
    """Read-only Phase 5 risk configuration and current daily baseline."""
    return get_risk_service(request).snapshot()
