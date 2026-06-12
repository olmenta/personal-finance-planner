"""AI onboarding interview endpoints (spec: ai-onboarding).

Fail-closed: a missing LLM key or a failed turn (after retry) surfaces as
503 onboarding_unavailable so the webapp can offer the starter-template
fallback (POST /onboarding/template). Transcript content never hits logs.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import OnboardingSession, User
from ..schemas import (
    OnboardingFinalizeRequest,
    OnboardingFinalizeResponse,
    OnboardingMessageRequest,
    OnboardingSessionOut,
    OnboardingStatusOut,
)
from ..services import onboarding
from ..services.category_setup import DEFAULT_CATEGORY_TREE, create_tree
from ..services.onboarding import OnboardingUnavailable

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _session_out(session: OnboardingSession) -> OnboardingSessionOut:
    return OnboardingSessionOut(
        id=session.id,
        status=session.status,
        prompt_version=session.prompt_version,
        transcript=session.transcript_json,
        proposal=session.proposal_json,
    )


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail={"code": "onboarding_unavailable"})


@router.post("/start", response_model=OnboardingSessionOut)
def start(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> OnboardingSessionOut:
    try:
        session = onboarding.start_session(db, user.id, user.locale)
    except OnboardingUnavailable:
        raise _unavailable() from None
    return _session_out(session)


@router.get("/status", response_model=OnboardingStatusOut)
def status(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> OnboardingStatusOut:
    """Lightweight flag pair for the dashboard entry capsule."""
    statuses = set(
        db.scalars(
            select(OnboardingSession.status).where(OnboardingSession.user_id == user.id)
        )
    )
    return OnboardingStatusOut(
        has_completed="completed" in statuses, has_active="active" in statuses
    )


@router.get("/session", response_model=OnboardingSessionOut)
def get_session(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> OnboardingSessionOut:
    session = onboarding.get_active_session(db, user.id)
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "no_active_session"})
    return _session_out(session)


@router.post("/messages", response_model=OnboardingSessionOut)
def send_message(
    payload: OnboardingMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> OnboardingSessionOut:
    session = onboarding.get_active_session(db, user.id)
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "no_active_session"})
    try:
        onboarding.advance(db, session, payload.message, user.locale)
    except OnboardingUnavailable:
        raise _unavailable() from None
    return _session_out(session)


@router.post("/{session_id}/finalize", response_model=OnboardingFinalizeResponse)
def finalize(
    session_id: str,
    payload: OnboardingFinalizeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> OnboardingFinalizeResponse:
    session = db.get(OnboardingSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "session_not_found"})
    if session.status != "active":
        raise HTTPException(status_code=409, detail={"code": "session_not_active"})
    categories_created, payees_created = onboarding.finalize(db, session, payload)
    return OnboardingFinalizeResponse(
        categories_created=categories_created, payees_created=payees_created
    )


@router.post("/template", response_model=OnboardingFinalizeResponse)
def use_template(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> OnboardingFinalizeResponse:
    """Starter-template fallback when the interview is unavailable:
    default tree, no transcript, no preferences document."""
    session = onboarding.get_active_session(db, user.id)
    if session is not None:
        session.status = "abandoned"
    created = create_tree(db, user.id, DEFAULT_CATEGORY_TREE)
    return OnboardingFinalizeResponse(categories_created=created, payees_created=0)
