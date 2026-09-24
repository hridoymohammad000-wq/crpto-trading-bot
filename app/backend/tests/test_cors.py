import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
)
def test_allowed_local_origins_receive_cors_header(origin: str) -> None:
    response = client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_unrelated_origin_is_not_allowed() -> None:
    response = client.get(
        "/health",
        headers={"Origin": "https://unrelated.example"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_preflight_request_allows_current_frontend_request() -> None:
    response = client.options(
        "/bot/start",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://127.0.0.1:3000"
    )
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Content-Type" in response.headers["access-control-allow-headers"]
    assert response.headers.get("access-control-allow-credentials") == "true"
