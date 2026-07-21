from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import TaskPriority


class RuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    rule_version: str
    triggered: bool
    priority: TaskPriority
    title: str
    reason: str
    evidence_reading_ids: list[str]
    evidence: dict[str, Any]
    sla_minutes: int = Field(ge=0)
    source_reference: str
