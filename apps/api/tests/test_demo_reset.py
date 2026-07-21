from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.main import app


def test_demo_reset_requires_secret_header_and_restores_seed(
    db_session: Session,
) -> None:
    def override_database() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_database
    client = TestClient(app)
    try:
        assert client.post("/api/v1/demo/reset").status_code == 403
        assert (
            client.post(
                "/api/v1/demo/reset",
                headers={"X-Demo-Reset-Token": "incorrect-token"},
            ).status_code
            == 403
        )

        response = client.post(
            "/api/v1/demo/reset",
            headers={
                "X-Demo-Reset-Token": get_settings().caresignal_demo_reset_token,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "reset"
        assert body["synthetic_data"] is True
        assert body["counts"] == {
            "users": 7,
            "patients": 4,
            "clinicians": 2,
            "submissions": 6,
            "readings": 6,
            "rule_evaluations": 1,
            "review_tasks": 1,
            "messages": 0,
            "audit_events": 1,
        }
        assert "token" not in body
    finally:
        app.dependency_overrides.clear()
