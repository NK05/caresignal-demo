from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import GenerationType, PatientMessage
from app.schemas import AIPatientDraft, GroundedCaseBrief
from app.seed import CLINICIAN_IDS, USER_IDS, seed_demo_data
from app.services.clinical_ai import ClinicalAIResult, get_clinical_ai_provider

NOW = datetime.now(UTC).replace(microsecond=0)
TASK_ID = "51000000-0000-4000-8000-000000000001"


class FakeClinicalAI:
    invalid_source = False

    def case_brief(self, payload: dict[str, object]) -> ClinicalAIResult:
        allowed = payload["allowed_source_record_ids"]
        assert isinstance(allowed, list) and allowed
        source_id = "00000000-0000-0000-0000-000000000000" if self.invalid_source else allowed[0]
        return ClinicalAIResult(
            value=GroundedCaseBrief(
                summary="Synthetic confirmed readings require clinician workflow review.",
                timeline_points=["A confirmed reading is present."],
                rule_explanation="The configured deterministic rule created this task.",
                adherence_context=None,
                missing_information=[],
                source_record_ids=[source_id],
                safety_note="AI-generated workflow summary; verify against source records.",
            ),
            request_id="resp_case_synthetic",
        )

    def patient_draft(self, payload: dict[str, object]) -> ClinicalAIResult:
        assert payload["clinician_outcome"] == "Follow-up reviewed by the clinician."
        return ClinicalAIResult(
            value=AIPatientDraft(
                language="nd",
                content="Ithimba lakho selihlole imininingwane. Sicela ulandele uhlelo oluvunyelwene lomtholampilo.",
                requires_clinician_approval=True,
            ),
            request_id="resp_draft_synthetic",
        )


@pytest.fixture
def ai_client(db_session: Session) -> Generator[tuple[TestClient, FakeClinicalAI], None, None]:
    seed_demo_data(db_session, now=NOW)
    db_session.commit()
    provider = FakeClinicalAI()

    def override_database() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_database
    app.dependency_overrides[get_clinical_ai_provider] = lambda: provider
    try:
        yield TestClient(app), provider
    finally:
        app.dependency_overrides.clear()


def headers(user: str = "doctor") -> dict[str, str]:
    return {"X-Demo-Session": USER_IDS[user]}


def start_review(client: TestClient) -> None:
    base = f"/api/v1/clinician/tasks/{TASK_ID}"
    assert client.post(f"{base}/assign", headers=headers(), json={"clinician_id": CLINICIAN_IDS["doctor"]}).status_code == 200
    assert client.post(f"{base}/acknowledge", headers=headers()).status_code == 200
    assert client.post(f"{base}/start-review", headers=headers()).status_code == 200


def test_case_brief_is_grounded_to_visible_source_ids(ai_client) -> None:
    client, provider = ai_client
    start_review(client)
    response = client.post(f"/api/v1/clinician/tasks/{TASK_ID}/case-brief", headers=headers())
    assert response.status_code == 200
    assert response.json()["safety_note"].startswith("AI-generated workflow summary")

    provider.invalid_source = True
    rejected = client.post(f"/api/v1/clinician/tasks/{TASK_ID}/case-brief", headers=headers())
    assert rejected.status_code == 409


def test_ai_patient_draft_still_requires_separate_approval(ai_client) -> None:
    client, _provider = ai_client
    start_review(client)
    base = f"/api/v1/clinician/tasks/{TASK_ID}"
    response = client.post(
        f"{base}/ai-draft-message",
        headers=headers(),
        json={"language": "nd", "clinician_outcome": "Follow-up reviewed by the clinician."},
    )
    assert response.status_code == 200
    message = response.json()["messages"][0]
    assert message["generation_type"] == GenerationType.AI_DRAFT
    assert message["approval_status"] == "draft"
    assert message["delivery_status"] == "not_sent"
    assert client.post(
        f"{base}/approve-message",
        headers=headers(),
        json={"message_id": message["message_id"], "send": True},
    ).status_code == 409


def test_ai_failure_is_safe_and_creates_no_patient_draft(
    ai_client, db_session: Session
) -> None:
    client, provider = ai_client
    start_review(client)
    before = db_session.scalar(select(func.count()).select_from(PatientMessage)) or 0

    def fail(_payload: dict[str, object]) -> ClinicalAIResult:
        raise TimeoutError("synthetic provider timeout")

    provider.patient_draft = fail  # type: ignore[method-assign]
    response = client.post(
        f"/api/v1/clinician/tasks/{TASK_ID}/ai-draft-message",
        headers=headers(),
        json={"language": "nd", "clinician_outcome": "Follow-up reviewed by the clinician."},
    )

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
    after = db_session.scalar(select(func.count()).select_from(PatientMessage)) or 0
    assert after == before


def test_clinical_ai_endpoints_reject_patient_role(ai_client) -> None:
    client, _provider = ai_client
    patient_headers = headers("rudo")
    assert client.post(
        f"/api/v1/clinician/tasks/{TASK_ID}/case-brief", headers=patient_headers
    ).status_code == 403
    assert client.post(
        f"/api/v1/clinician/tasks/{TASK_ID}/ai-draft-message",
        headers=patient_headers,
        json={"language": "nd", "clinician_outcome": "Synthetic outcome."},
    ).status_code == 403
