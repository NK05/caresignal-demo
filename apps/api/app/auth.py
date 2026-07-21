from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClinicianProfile, PatientProfile, User, UserRole

DatabaseSession = Annotated[Session, Depends(get_db)]
DemoSessionHeader = Annotated[str | None, Header(alias="X-Demo-Session")]


def get_current_user(
    db: DatabaseSession,
    session_token: DemoSessionHeader = None,
) -> User:
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo session required",
        )

    user = db.get(User, session_token)
    if user is None or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid demo session",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_patient(current_user: CurrentUser) -> PatientProfile:
    if current_user.role is not UserRole.PATIENT or current_user.patient_profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patient role required",
        )
    return current_user.patient_profile


CurrentPatient = Annotated[PatientProfile, Depends(require_patient)]


def require_clinician(current_user: CurrentUser) -> ClinicianProfile:
    if current_user.role is not UserRole.CLINICIAN or current_user.clinician_profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinician role required",
        )
    return current_user.clinician_profile


CurrentClinician = Annotated[ClinicianProfile, Depends(require_clinician)]
