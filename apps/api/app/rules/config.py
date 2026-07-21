from dataclasses import dataclass

from app.models import TaskPriority

RULESET_VERSION = "demo-2026.07.1"
SOURCE_REFERENCE = (
    "docs/CARESIGNAL_DEMO_RULES.md — illustrative prototype configuration; not clinically validated"
)


@dataclass(frozen=True)
class SingleReadingConfig:
    systolic: int = 180
    diastolic: int = 120
    priority: TaskPriority = TaskPriority.URGENT_REVIEW
    sla_minutes: int = 30


@dataclass(frozen=True)
class RepeatedReadingConfig:
    systolic: int = 150
    diastolic: int = 95
    minimum_count: int = 3
    window_days: int = 7
    priority: TaskPriority = TaskPriority.NEEDS_REVIEW
    sla_minutes: int = 240


@dataclass(frozen=True)
class SustainedPatternConfig:
    average_systolic: int = 145
    average_diastolic: int = 90
    minimum_count: int = 3
    window_days: int = 14
    priority: TaskPriority = TaskPriority.NEEDS_REVIEW
    sla_minutes: int = 480


@dataclass(frozen=True)
class WorseningPatternConfig:
    systolic_delta: int = 10
    diastolic_delta: int = 8
    minimum_count: int = 3
    window_days: int = 7
    priority: TaskPriority = TaskPriority.WATCH
    sla_minutes: int = 720


@dataclass(frozen=True)
class AdherenceFollowUpConfig:
    priority: TaskPriority = TaskPriority.NEEDS_REVIEW
    sla_minutes: int = 1440


@dataclass(frozen=True)
class ContextFollowUpConfig:
    review_codes: frozenset[str] = frozenset({"feeling_unwell"})
    priority: TaskPriority = TaskPriority.NEEDS_REVIEW
    sla_minutes: int = 120


@dataclass(frozen=True)
class MissedReadingConfig:
    gap_days: int = 7
    priority: TaskPriority = TaskPriority.WATCH
    sla_minutes: int = 1440


@dataclass(frozen=True)
class DemoRuleSet:
    version: str = RULESET_VERSION
    source_reference: str = SOURCE_REFERENCE
    single: SingleReadingConfig = SingleReadingConfig()
    repeated: RepeatedReadingConfig = RepeatedReadingConfig()
    sustained: SustainedPatternConfig = SustainedPatternConfig()
    worsening: WorseningPatternConfig = WorseningPatternConfig()
    adherence: AdherenceFollowUpConfig = AdherenceFollowUpConfig()
    context: ContextFollowUpConfig = ContextFollowUpConfig()
    missed: MissedReadingConfig = MissedReadingConfig()


DEMO_RULESET = DemoRuleSet()
