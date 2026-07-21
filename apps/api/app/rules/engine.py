from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BloodPressureReading,
    MedicationStatus,
    RuleEvaluation,
    TaskPriority,
)
from app.rules.config import DEMO_RULESET, DemoRuleSet
from app.rules.contracts import RuleResult


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _deduplicated_history(
    readings: list[BloodPressureReading],
) -> list[BloodPressureReading]:
    by_id = {reading.id: reading for reading in readings}
    return sorted(by_id.values(), key=lambda reading: (_utc(reading.measured_at), reading.id))


def _window(
    readings: list[BloodPressureReading],
    *,
    end: datetime,
    days: int,
) -> list[BloodPressureReading]:
    window_end = _utc(end)
    window_start = window_end - timedelta(days=days)
    return [
        reading for reading in readings if window_start <= _utc(reading.measured_at) <= window_end
    ]


def _observed_values(readings: list[BloodPressureReading]) -> list[dict[str, object]]:
    return [
        {
            "reading_id": reading.id,
            "systolic": reading.systolic,
            "diastolic": reading.diastolic,
            "measured_at": _utc(reading.measured_at).isoformat(),
        }
        for reading in readings
    ]


def _result(
    *,
    rule_id: str,
    title: str,
    triggered: bool,
    configured_priority: TaskPriority,
    configured_sla_minutes: int,
    reason: str,
    readings: list[BloodPressureReading],
    evidence: dict[str, object],
    ruleset: DemoRuleSet,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_version=ruleset.version,
        triggered=triggered,
        priority=configured_priority if triggered else TaskPriority.ROUTINE,
        title=title,
        reason=reason,
        evidence_reading_ids=[reading.id for reading in readings],
        evidence={
            **evidence,
            "observed_values": _observed_values(readings),
            "configured_priority": configured_priority.value,
            "illustrative_not_clinically_validated": True,
        },
        sla_minutes=configured_sla_minutes if triggered else 0,
        source_reference=ruleset.source_reference,
    )


def evaluate_reading(
    current: BloodPressureReading,
    history: list[BloodPressureReading],
    *,
    ruleset: DemoRuleSet = DEMO_RULESET,
) -> list[RuleResult]:
    ordered = _deduplicated_history([*history, current])
    current_time = _utc(current.measured_at)
    results: list[RuleResult] = []

    single_triggered = (
        current.systolic >= ruleset.single.systolic or current.diastolic >= ruleset.single.diastolic
    )
    results.append(
        _result(
            rule_id="demo.single-reading-review",
            title="Single-reading review marker",
            triggered=single_triggered,
            configured_priority=ruleset.single.priority,
            configured_sla_minutes=ruleset.single.sla_minutes,
            reason=(
                f"Confirmed reading {current.systolic}/{current.diastolic} "
                f"{'met' if single_triggered else 'did not meet'} the configured demo marker "
                f"of systolic ≥{ruleset.single.systolic} or "
                f"diastolic ≥{ruleset.single.diastolic}."
            ),
            readings=[current],
            evidence={
                "thresholds": {
                    "systolic": ruleset.single.systolic,
                    "diastolic": ruleset.single.diastolic,
                    "operator": "either_greater_than_or_equal",
                },
                "window_start": current_time.isoformat(),
                "window_end": current_time.isoformat(),
            },
            ruleset=ruleset,
        )
    )

    repeated_window = _window(
        ordered,
        end=current_time,
        days=ruleset.repeated.window_days,
    )
    repeated_matches = [
        reading
        for reading in repeated_window
        if reading.systolic >= ruleset.repeated.systolic
        or reading.diastolic >= ruleset.repeated.diastolic
    ]
    repeated_triggered = len(repeated_matches) >= ruleset.repeated.minimum_count
    results.append(
        _result(
            rule_id="demo.repeated-reading-pattern",
            title="Repeated reading pattern",
            triggered=repeated_triggered,
            configured_priority=ruleset.repeated.priority,
            configured_sla_minutes=ruleset.repeated.sla_minutes,
            reason=(
                f"{len(repeated_matches)} confirmed reading(s) in the last "
                f"{ruleset.repeated.window_days} days met the configured demo marker; "
                f"{ruleset.repeated.minimum_count} are required."
            ),
            readings=repeated_matches,
            evidence={
                "thresholds": {
                    "systolic": ruleset.repeated.systolic,
                    "diastolic": ruleset.repeated.diastolic,
                    "minimum_count": ruleset.repeated.minimum_count,
                },
                "window_start": (
                    current_time - timedelta(days=ruleset.repeated.window_days)
                ).isoformat(),
                "window_end": current_time.isoformat(),
            },
            ruleset=ruleset,
        )
    )

    sustained_window = _window(
        ordered,
        end=current_time,
        days=ruleset.sustained.window_days,
    )
    average_systolic = mean(reading.systolic for reading in sustained_window)
    average_diastolic = mean(reading.diastolic for reading in sustained_window)
    sustained_triggered = len(sustained_window) >= ruleset.sustained.minimum_count and (
        average_systolic >= ruleset.sustained.average_systolic
        or average_diastolic >= ruleset.sustained.average_diastolic
    )
    results.append(
        _result(
            rule_id="demo.sustained-average-pattern",
            title="Average reading pattern",
            triggered=sustained_triggered,
            configured_priority=ruleset.sustained.priority,
            configured_sla_minutes=ruleset.sustained.sla_minutes,
            reason=(
                f"{len(sustained_window)} confirmed reading(s) in the last "
                f"{ruleset.sustained.window_days} days had averages of "
                f"{average_systolic:.1f}/{average_diastolic:.1f}; "
                f"{ruleset.sustained.minimum_count} readings and a configured average marker "
                f"of systolic ≥{ruleset.sustained.average_systolic} or "
                f"diastolic ≥{ruleset.sustained.average_diastolic} are required."
            ),
            readings=sustained_window,
            evidence={
                "average_systolic": round(average_systolic, 1),
                "average_diastolic": round(average_diastolic, 1),
                "minimum_count": ruleset.sustained.minimum_count,
                "window_start": (
                    current_time - timedelta(days=ruleset.sustained.window_days)
                ).isoformat(),
                "window_end": current_time.isoformat(),
            },
            ruleset=ruleset,
        )
    )

    worsening_window = _window(
        ordered,
        end=current_time,
        days=ruleset.worsening.window_days,
    )
    oldest = worsening_window[0]
    newest = worsening_window[-1]
    systolic_delta = newest.systolic - oldest.systolic
    diastolic_delta = newest.diastolic - oldest.diastolic
    worsening_triggered = len(worsening_window) >= ruleset.worsening.minimum_count and (
        systolic_delta >= ruleset.worsening.systolic_delta
        or diastolic_delta >= ruleset.worsening.diastolic_delta
    )
    results.append(
        _result(
            rule_id="demo.worsening-reading-pattern",
            title="Reading change pattern",
            triggered=worsening_triggered,
            configured_priority=ruleset.worsening.priority,
            configured_sla_minutes=ruleset.worsening.sla_minutes,
            reason=(
                f"Across {len(worsening_window)} confirmed reading(s), the oldest-to-newest "
                f"change was systolic {systolic_delta:+d} and diastolic {diastolic_delta:+d}; "
                f"the configured demo change markers are +{ruleset.worsening.systolic_delta} "
                f"or +{ruleset.worsening.diastolic_delta}."
            ),
            readings=worsening_window,
            evidence={
                "systolic_delta": systolic_delta,
                "diastolic_delta": diastolic_delta,
                "minimum_count": ruleset.worsening.minimum_count,
                "window_start": (
                    current_time - timedelta(days=ruleset.worsening.window_days)
                ).isoformat(),
                "window_end": current_time.isoformat(),
            },
            ruleset=ruleset,
        )
    )

    adherence_triggered = current.medication_taken is MedicationStatus.NO
    results.append(
        _result(
            rule_id="demo.medication-follow-up",
            title="Medication follow-up marker",
            triggered=adherence_triggered,
            configured_priority=ruleset.adherence.priority,
            configured_sla_minutes=ruleset.adherence.sla_minutes,
            reason=(
                "The patient recorded medication_taken=no for this confirmed reading."
                if adherence_triggered
                else "The patient did not record medication_taken=no for this confirmed reading."
            ),
            readings=[current],
            evidence={
                "medication_taken": current.medication_taken.value,
                "missed_medication_reason_code": current.missed_medication_reason_code,
                "window_start": current_time.isoformat(),
                "window_end": current_time.isoformat(),
            },
            ruleset=ruleset,
        )
    )

    matched_context_codes = sorted(set(current.context_codes) & ruleset.context.review_codes)
    context_triggered = bool(matched_context_codes)
    results.append(
        _result(
            rule_id="demo.context-follow-up",
            title="Context follow-up marker",
            triggered=context_triggered,
            configured_priority=ruleset.context.priority,
            configured_sla_minutes=ruleset.context.sla_minutes,
            reason=(
                f"Configured context code(s) were recorded: {', '.join(matched_context_codes)}."
                if context_triggered
                else "No configured context follow-up code was recorded for this reading."
            ),
            readings=[current],
            evidence={
                "matched_context_codes": matched_context_codes,
                "configured_context_codes": sorted(ruleset.context.review_codes),
                "window_start": current_time.isoformat(),
                "window_end": current_time.isoformat(),
            },
            ruleset=ruleset,
        )
    )
    return results


def evaluate_missed_reading(
    *,
    patient_id: str,
    last_reading: BloodPressureReading | None,
    as_of: datetime,
    ruleset: DemoRuleSet = DEMO_RULESET,
) -> RuleResult:
    now = _utc(as_of)
    if last_reading is None:
        return _result(
            rule_id="demo.expected-reading-gap",
            title="Expected reading gap",
            triggered=False,
            configured_priority=ruleset.missed.priority,
            configured_sla_minutes=ruleset.missed.sla_minutes,
            reason=(
                "No confirmed baseline reading is available, so the demo gap rule cannot evaluate."
            ),
            readings=[],
            evidence={
                "patient_id": patient_id,
                "configured_gap_days": ruleset.missed.gap_days,
                "window_start": now.isoformat(),
                "window_end": now.isoformat(),
            },
            ruleset=ruleset,
        )

    gap = now - _utc(last_reading.measured_at)
    triggered = gap >= timedelta(days=ruleset.missed.gap_days)
    return _result(
        rule_id="demo.expected-reading-gap",
        title="Expected reading gap",
        triggered=triggered,
        configured_priority=ruleset.missed.priority,
        configured_sla_minutes=ruleset.missed.sla_minutes,
        reason=(
            f"The last confirmed reading was {gap.total_seconds() / 86400:.1f} days ago; "
            f"the configured demo gap is {ruleset.missed.gap_days} days."
        ),
        readings=[last_reading],
        evidence={
            "patient_id": patient_id,
            "gap_seconds": int(gap.total_seconds()),
            "configured_gap_days": ruleset.missed.gap_days,
            "window_start": _utc(last_reading.measured_at).isoformat(),
            "window_end": now.isoformat(),
        },
        ruleset=ruleset,
    )


def evaluate_confirmed_reading(
    db: Session,
    *,
    reading: BloodPressureReading,
    evaluated_at: datetime,
    ruleset: DemoRuleSet = DEMO_RULESET,
) -> list[RuleEvaluation]:
    history = list(
        db.scalars(
            select(BloodPressureReading).where(
                BloodPressureReading.patient_id == reading.patient_id
            )
        )
    )
    results = evaluate_reading(reading, history, ruleset=ruleset)
    evaluations = [
        RuleEvaluation(
            patient_id=reading.patient_id,
            reading_id=reading.id,
            rule_id=result.rule_id,
            rule_version=result.rule_version,
            triggered=result.triggered,
            priority=result.priority,
            reason=result.reason,
            evidence={
                **result.evidence,
                "title": result.title,
                "evidence_reading_ids": result.evidence_reading_ids,
                "sla_minutes": result.sla_minutes,
            },
            source_reference=result.source_reference,
            evaluated_at=evaluated_at,
        )
        for result in results
    ]
    db.add_all(evaluations)
    db.flush()
    return evaluations
