from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_identifies_service() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "caresignal-api",
        "status": "ok",
        "documentation": "/docs",
    }


def test_health_endpoint_is_stable() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "caresignal-api",
        "status": "ok",
        "version": "0.1.0",
        "environment": "development",
    }
