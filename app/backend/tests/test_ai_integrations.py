from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_ai_status_reports_analysis_only_mode() -> None:
    old_enabled = settings.AI_ENABLED
    old_key = settings.GROQ_API_KEY
    try:
        settings.AI_ENABLED = False
        settings.GROQ_API_KEY = ""
        with TestClient(app) as client:
            response = client.get("/ai/status")
            assert response.status_code == 200
            payload = response.json()
            assert payload["mode"] == "analysis_only"
            assert payload["enabled"] is False
            assert payload["configured"] is False
    finally:
        settings.AI_ENABLED = old_enabled
        settings.GROQ_API_KEY = old_key


def test_ai_analyze_fails_closed_when_disabled() -> None:
    old_enabled = settings.AI_ENABLED
    try:
        settings.AI_ENABLED = False
        with TestClient(app) as client:
            response = client.post("/ai/analyze", json={"context": {"performance": {"totalTrades": 3}}})
            assert response.status_code == 503
            assert "disabled" in response.json()["detail"].lower()
    finally:
        settings.AI_ENABLED = old_enabled


def test_integrations_status_never_returns_secret_values() -> None:
    old_ai_key = settings.GROQ_API_KEY
    old_bybit_key = settings.BYBIT_API_KEY
    old_bybit_secret = settings.BYBIT_API_SECRET
    try:
        settings.GROQ_API_KEY = "super-secret-groq-key"
        settings.BYBIT_API_KEY = "bybit-key"
        settings.BYBIT_API_SECRET = "bybit-secret"
        with TestClient(app) as client:
            response = client.get("/integrations/status")
            assert response.status_code == 200
            payload = response.json()
            raw = response.text
            assert payload["ai"]["configured"] is True
            assert payload["bybit"]["configured"] is True
            assert "super-secret-groq-key" not in raw
            assert "bybit-key" not in raw
            assert "bybit-secret" not in raw
    finally:
        settings.GROQ_API_KEY = old_ai_key
        settings.BYBIT_API_KEY = old_bybit_key
        settings.BYBIT_API_SECRET = old_bybit_secret
