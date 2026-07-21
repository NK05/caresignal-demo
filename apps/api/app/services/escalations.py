from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, ReviewTask, TaskStatus
from app.schemas import EscalationRunResponse


def run_overdue_escalations(db: Session, *, now: datetime) -> EscalationRunResponse:
    active = {TaskStatus.OPEN, TaskStatus.ASSIGNED, TaskStatus.IN_REVIEW}
    tasks = list(
        db.scalars(
            select(ReviewTask)
            .where(
                ReviewTask.status.in_(active),
                ReviewTask.due_at.is_not(None),
                ReviewTask.due_at < now,
            )
            .order_by(ReviewTask.due_at.asc(), ReviewTask.id.asc())
        )
    )
    new_ids: list[str] = []
    for task in tasks:
        already_recorded = db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.entity_type == "review_task",
                AuditEvent.entity_id == task.id,
                AuditEvent.event_type == "review_task.overdue_escalated",
            )
        )
        if already_recorded is not None:
            continue
        db.add(
            AuditEvent(
                actor_user_id=None,
                patient_id=task.patient_id,
                entity_type="review_task",
                entity_id=task.id,
                event_type="review_task.overdue_escalated",
                event_metadata={
                    "due_at": task.due_at.isoformat() if task.due_at else None,
                    "priority_unchanged": True,
                    "automatic_patient_message": False,
                },
                created_at=now,
            )
        )
        new_ids.append(task.id)
    db.commit()
    return EscalationRunResponse(
        overdue_active_tasks=len(tasks),
        newly_escalated_tasks=len(new_ids),
        task_ids=new_ids,
    )
