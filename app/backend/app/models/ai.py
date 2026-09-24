from typing import Any

from pydantic import BaseModel, Field


class AIAnalysisRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)
    question: str | None = Field(default=None, max_length=1000)


class AIAnalysisResponse(BaseModel):
    analysis: str
    provider: str
    model: str
    mode: str = "analysis_only"
