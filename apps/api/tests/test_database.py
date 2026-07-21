from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.models import Language, PatientProfile, ReviewTask, TaskPriority, User
from app.seed import PATIENT_IDS, USER_IDS, reset_demo_data, seed_demo_data

EXPECTED_TABLES = {
    "audit_events",
    "blood_pressure_readings",
    "clinician_profiles",
    "contact_attempts",
    "patient_messages",
    "patient_profiles",
    "reading_submissions",
    "review_tasks",
    "rule_evaluations",
    "task_evidence",
    "users",
}
EXPECTED_COUNTS = {
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
FIXED_NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


def test_initial_migration_creates_and_downgrades_schema(tmp_path: Path) -> None:
    api_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "migration.db"
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    from app.database import create_database_engine

    engine = create_database_engine(f"sqlite:///{database_path}")
    assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))
    rule_evaluation_unique_constraints = {
        constraint["name"]
        for constraint in inspect(engine).get_unique_constraints("rule_evaluations")
    }
    assert "uq_rule_evaluation_reading_rule_version" in rule_evaluation_unique_constraints

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()


def test_seed_data_is_synthetic_and_covers_required_demo_scenarios(
    db_session: Session,
) -> None:
    counts = seed_demo_data(db_session, now=FIXED_NOW)
    db_session.commit()

    assert counts == EXPECTED_COUNTS
    assert db_session.get(User, USER_IDS["rudo"]).preferred_language is Language.NDEBELE
    assert db_session.get(User, USER_IDS["tawanda"]).preferred_language is Language.SHONA
    assert db_session.get(User, USER_IDS["tariro"]).preferred_language is Language.ENGLISH

    task = db_session.scalar(select(ReviewTask))
    assert task is not None
    assert task.patient_id == PATIENT_IDS["nomsa"]
    assert task.priority is TaskPriority.URGENT_REVIEW
    assert task.due_at is not None and task.due_at < FIXED_NOW.replace(tzinfo=None)

    patient_columns = set(PatientProfile.__table__.columns.keys())
    assert patient_columns.isdisjoint({"address", "national_id", "hiv_status", "phone_number"})


def test_reset_removes_mutations_and_restores_known_ids(db_session: Session) -> None:
    seed_demo_data(db_session, now=FIXED_NOW)
    db_session.add(
        User(
            id="99999999-0000-4000-8000-000000000001",
            display_name="Temporary Synthetic User",
            role="demo_admin",
            preferred_language="en",
        )
    )
    db_session.commit()

    counts = reset_demo_data(db_session, now=FIXED_NOW)
    db_session.commit()

    assert counts == EXPECTED_COUNTS
    assert db_session.get(User, "99999999-0000-4000-8000-000000000001") is None
    assert db_session.get(User, USER_IDS["tariro"]) is not None


def test_foreign_keys_prevent_orphan_patient_profiles(db_session: Session) -> None:
    db_session.add(
        PatientProfile(
            user_id="missing-user",
            synthetic_identifier="CS-PAT-ORPHAN",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()
