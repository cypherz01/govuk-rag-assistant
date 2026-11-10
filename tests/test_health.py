from fastapi.testclient import TestClient

from govuk_rag import __version__


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": __version__,
        "environment": "test",
    }


def test_health_is_described_in_openapi_schema(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "/health" in schema["paths"]
    assert "HealthResponse" in schema["components"]["schemas"]
