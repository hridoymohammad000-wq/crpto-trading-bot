from typing import cast

from fastapi import APIRouter, HTTPException, Request

from app.ai import AIAnalysisService
from app.models.ai import AIAnalysisRequest, AIAnalysisResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
async def ai_status(request: Request) -> dict:
    service = cast(AIAnalysisService, request.app.state.ai_analysis_service)
    return service.status()


@router.post("/analyze", response_model=AIAnalysisResponse)
async def ai_analyze(payload: AIAnalysisRequest, request: Request) -> AIAnalysisResponse:
    service = cast(AIAnalysisService, request.app.state.ai_analysis_service)
    try:
        analysis = await service.analyze(payload.context, payload.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI provider request failed") from exc

    status = service.status()
    return AIAnalysisResponse(
        analysis=analysis,
        provider=status["provider"],
        model=status["model"],
    )
