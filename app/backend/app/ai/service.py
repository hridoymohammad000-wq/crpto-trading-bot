import json
from typing import Any

import httpx

from app.core.config import Settings


class AIAnalysisService:
    """Optional read-only AI analyst.

    This service cannot place orders, approve risk, change SL/TP,
    bypass readiness, or call exchange execution APIs.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self._settings.AI_ENABLED)

    @property
    def configured(self) -> bool:
        return bool(self._settings.GROQ_API_KEY.strip())

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "provider": self._settings.AI_PROVIDER,
            "model": self._settings.AI_MODEL,
            "mode": "analysis_only",
        }

    async def analyze(
        self,
        context: dict[str, Any],
        question: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("AI analyst is disabled")
        if not self.configured:
            raise RuntimeError("GROQ_API_KEY is not configured")
        if self._settings.AI_PROVIDER.lower() != "groq":
            raise RuntimeError(
                "Unsupported AI_PROVIDER; this build is configured for Groq"
            )

        instructions = (
            "You are a READ-ONLY analyst for a Bybit Demo trading bot. "
            "Analyze only supplied facts. Never claim to place, approve, block, "
            "modify, or execute orders. Deterministic strategy/risk/readiness/execution "
            "remain authoritative. Missing values are unavailable, never zero. "
            "Prefer scannerStatus, scannerCandidates, scannerWatchlist, botRuntime, "
            "openPositions, recentSignals and metrics as factual sources. "
            "Return ONLY one valid JSON object with keys: "
            "analysis (string), action (ALLOW|CAUTION|BLOCK|null), "
            "confidence (integer 0-100|null), market_regime (string|null), "
            "symbol (string|null). "
            "ALLOW/CAUTION/BLOCK is advisory analysis only, never an execution command. "
            "If evidence is insufficient, use null rather than inventing facts."
        )

        user_payload = {
            "question": question
            or "Review this snapshot and identify useful observations and risks.",
            "snapshot": context,
        }

        url = f"{self._settings.AI_BASE_URL.rstrip('/')}/responses"
        headers = {
            "Authorization": f"Bearer {self._settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._settings.AI_MODEL,
            "instructions": instructions,
            "input": json.dumps(user_payload, default=str),
            "max_output_tokens": self._settings.AI_MAX_OUTPUT_TOKENS,
        }

        async with httpx.AsyncClient(
            timeout=self._settings.AI_TIMEOUT_SECONDS
        ) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        raw_text = self._extract_text(data)
        parsed = self._parse_structured(raw_text)

        fallback_symbol = context.get("selectedSymbol")
        if parsed.get("symbol") is None and isinstance(fallback_symbol, str):
            parsed["symbol"] = fallback_symbol

        return parsed

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        if (
            isinstance(data.get("output_text"), str)
            and data["output_text"].strip()
        ):
            return data["output_text"].strip()

        parts: list[str] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if (
                    content.get("type") in {"output_text", "text"}
                    and isinstance(content.get("text"), str)
                ):
                    parts.append(content["text"])

        text = "\n".join(
            part.strip() for part in parts if part.strip()
        )

        if not text:
            raise RuntimeError("AI provider returned no text output")

        return text

    @staticmethod
    def _parse_structured(raw_text: str) -> dict[str, Any]:
        cleaned = raw_text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            payload = json.loads(cleaned)
        except Exception:
            return {
                "analysis": raw_text,
                "action": None,
                "confidence": None,
                "market_regime": None,
                "symbol": None,
            }

        if not isinstance(payload, dict):
            return {
                "analysis": raw_text,
                "action": None,
                "confidence": None,
                "market_regime": None,
                "symbol": None,
            }

        action = payload.get("action")
        if action not in {"ALLOW", "CAUTION", "BLOCK"}:
            action = None

        confidence = payload.get("confidence")
        try:
            confidence = int(confidence) if confidence is not None else None
        except Exception:
            confidence = None

        if confidence is not None:
            confidence = max(0, min(100, confidence))

        return {
            "analysis": str(payload.get("analysis") or raw_text),
            "action": action,
            "confidence": confidence,
            "market_regime": (
                str(payload["market_regime"])
                if payload.get("market_regime") is not None
                else None
            ),
            "symbol": (
                str(payload["symbol"])
                if payload.get("symbol") is not None
                else None
            ),
        }
