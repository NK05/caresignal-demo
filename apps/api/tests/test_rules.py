from datetime import UTC, datetime, timedelta

import pytest

from app.models import BloodPressureReading, MedicationStatus, TaskPriority
from app.rules.config import DEMO_RULESET, RULESET_VERSION
from app.rules.engine import evaluate_missed_reading, evaluate_reading

ANCHOR = datetime(2026, 7, 17, 12, tzinfo=UTC)
PATIENT_ID = "11000000-0000-4000-8000-000000000099"


def _reading(
    key: int,
    systolic: int,
    diastolic: int,
    *,
    days_ago: float = 0,
    medication_taken: MedicationStatus = MedicationStatus.YES,
    context_codes: list[str] | None = None,
) -> BloodPressureReading:
    measured_at = ANCHOR - timedelta(days=days_ago)
    return BloodPressureReading(
        id=f"71000000-0000-4000-8000-{key:012d}",
        patient_id=PATIENT_ID,
        submission_id=f"70000000-0000-4000-8000-{key:012d}",
        systolic=systolic,
        diastolic=diastolic,
        measured_at=measured_at,
        medication_taken=medication_taken,
        context_codes=context_codes or [],
        confirmed_at=measured_at + timedelta(minutes=1),
    )


def _by_id(results, rule_id: str):  # noqa: ANN001, ANN202
    return next(result for result in results if result.rule_id == rule_id)


def test_single_reading_rule_triggers_at_exact_boundary_not_below() -> None:
    at_boundary = _reading(1, 180, 119)
    below = _reading(2, 179, 119)

    triggered = _by_id(
        evaluate_reading(at_boundary, [at_boundary]),
        "demo.single-reading-review",
    )
    not_triggered = _by_id(
        evaluate_reading(below, [below]),
        "demo.single-reading-review",
    )

    assert triggered.triggered is True
    assert triggered.priority is TaskPriority.URGENT_REVIEW
    assert triggered.sla_minutes == 30
    assert not_triggered.triggered is False
    assert not_triggered.priority is TaskPriority.ROUTINE
    assert not_triggered.sla_minutes == 0


def test_repeated_rule_requires_three_matching_readings_inside_window() -> None:
    readings = [
        _reading(1, 150, 80, days_ago=6),
        _reading(2, 140, 95, days_ago=3),
        _reading(3, 150, 95),
    ]
    result = _by_id(
        evaluate_reading(readings[-1], readings),
        "demo.repeated-reading-pattern",
    )
    only_two = _by_id(
        evaluate_reading(readings[-1], [readings[1], readings[2]]),
        "demo.repeated-reading-pattern",
    )

    assert result.triggered is True
    assert result.evidence_reading_ids == [reading.id for reading in readings]
    assert only_two.triggered is False


def test_sustained_average_rule_checks_count_window_and_average() -> None:
    readings = [
        _reading(1, 145, 88, days_ago=13),
        _reading(2, 146, 89, days_ago=6),
        _reading(3, 144, 93),
    ]
    result = _by_id(
        evaluate_reading(readings[-1], readings),
        "demo.sustained-average-pattern",
    )

    assert result.triggered is True
    assert result.evidence["average_systolic"] == 145.0
    assert result.evidence["average_diastolic"] == 90.0


def test_worsening_rule_uses_oldest_to_newest_change_at_boundary() -> None:
    readings = [
        _reading(1, 140, 84, days_ago=6),
        _reading(2, 145, 87, days_ago=3),
        _reading(3, 150, 92),
    ]
    result = _by_id(
        evaluate_reading(readings[-1], readings),
        "demo.worsening-reading-pattern",
    )

    assert result.triggered is True
    assert result.priority is TaskPriority.WATCH
    assert result.evidence["systolic_delta"] == 10
    assert result.evidence["diastolic_delta"] == 8


@pytest.mark.parametrize(
    ("medication", "context_codes", "rule_id"),
    [
        (MedicationStatus.NO, [], "demo.medication-follow-up"),
        (MedicationStatus.YES, ["feeling_unwell"], "demo.context-follow-up"),
    ],
)
def test_closed_structured_follow_up_rules(
    medication: MedicationStatus,
    context_codes: list[str],
    rule_id: str,
) -> None:
    reading = _reading(
        1,
        130,
        82,
        medication_taken=medication,
        context_codes=context_codes,
    )

    result = _by_id(evaluate_reading(reading, [reading]), rule_id)

    assert result.triggered is True
    assert result.priority is TaskPriority.NEEDS_REVIEW


def test_expected_reading_gap_rule_has_exact_time_boundary() -> None:
    last_reading = _reading(1, 130, 82, days_ago=7)
    at_boundary = evaluate_missed_reading(
        patient_id=PATIENT_ID,
        last_reading=last_reading,
        as_of=ANCHOR,
    )
    just_before = evaluate_missed_reading(
        patient_id=PATIENT_ID,
        last_reading=last_reading,
        as_of=ANCHOR - timedelta(seconds=1),
    )

    assert at_boundary.triggered is True
    assert at_boundary.priority is TaskPriority.WATCH
    assert just_before.triggered is False


def test_results_are_versioned_explainable_and_deterministic() -> None:
    readings = [
        _reading(1, 158, 99, days_ago=5),
        _reading(2, 161, 101, days_ago=3),
        _reading(3, 168, 105),
    ]

    first = evaluate_reading(readings[-1], readings)
    second = evaluate_reading(readings[-1], list(reversed(readings)))

    assert [result.model_dump(mode="json") for result in first] == [
        result.model_dump(mode="json") for result in second
    ]
    assert len(first) == 6
    for result in first:
        assert result.rule_version == RULESET_VERSION
        assert result.reason
        assert "not clinically validated" in result.source_reference
        assert result.evidence["illustrative_not_clinically_validated"] is True
        assert result.evidence["configured_priority"]
    assert DEMO_RULESET.version == RULESET_VERSION
