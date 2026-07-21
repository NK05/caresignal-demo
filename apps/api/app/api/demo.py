import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import DemoResetResponse, DemoSessionRequest, DemoSessionResponse
from app.seed import reset_demo_data

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/session", response_model=DemoSessionResponse)
def select_demo_session(
    request: DemoSessionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> DemoSessionResponse:
    user = db.get(User, request.user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo persona not found")

    return DemoSessionResponse(
        session_token=user.id,
        user_id=user.id,
        display_name=user.display_name,
        role=user.role,
        preferred_language=user.preferred_language,
    )


@router.post("/reset", response_model=DemoResetResponse)
def reset_demo(
    db: Annotated[Session, Depends(get_db)],
    reset_token: Annotated[str | None, Header(alias="X-Demo-Reset-Token")] = None,
) -> DemoResetResponse:
    settings = get_settings()
    if not settings.caresignal_demo_reset_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if reset_token is None or not secrets.compare_digest(
        reset_token, settings.caresignal_demo_reset_token
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid reset token")

    try:
        counts = reset_demo_data(db)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return DemoResetResponse(status="reset", synthetic_data=True, counts=counts)
