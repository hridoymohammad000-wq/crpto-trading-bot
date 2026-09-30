from typing import Any, Literal

from pydantic import BaseModel, Field


class AIAnalysisRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)
    question: str | None = Field(default=None, max_length=1000)


class AIAnalysisResponse(BaseModel):
    analysis: str
    provider: str
    model: str
    mode: str = "analysis_only"

    action: Literal["ALLOW", "CAUTION", "BLOCK"] | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    market_regime: str | None = None
    symbol: str | None = None
