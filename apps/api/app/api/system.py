import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import utc_now
from app.schemas import EscalationRunResponse
from app.services.escalations import run_overdue_escalations

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.post("/escalations/run", response_model=EscalationRunResponse)
def run_escalations(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Header(alias="X-Demo-System-Token")] = None,
) -> EscalationRunResponse:
    settings = get_settings()
    if token is None or not secrets.compare_digest(token, settings.caresignal_demo_reset_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid system token")
    return run_overdue_escalations(db, now=utc_now())
