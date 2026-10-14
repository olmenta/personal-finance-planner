"""Coach proposals: list, dismiss for a week, accept a raise or lower
(spec: coach-proposals)."""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import AcceptProposalIn, CoachProposalsView
from ..services import coach as service

router = APIRouter(prefix="/coach", tags=["coach"])


def _fail(error: service.CoachError) -> HTTPException:
    detail: dict = {"code": error.code}
    if error.proposal is not None:
        detail["proposal"] = service.proposal_out(error.proposal).model_dump()
    return HTTPException(status_code=error.status, detail=detail)


@router.get("/proposals", response_model=CoachProposalsView)
def list_proposals(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> CoachProposalsView:
    proposals = service.visible(db, user)
    return CoachProposalsView(proposals=[service.proposal_out(p) for p in proposals], total=len(proposals))


@router.post("/proposals/{fingerprint}/dismiss", status_code=204)
def dismiss(
    fingerprint: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> None:
    try:
        service.dismiss(db, user, fingerprint)
    except service.CoachError as error:
        raise _fail(error) from error


@router.post("/proposals/{fingerprint}/accept", response_model=CoachProposalsView)
def accept(
    fingerprint: str,
    body: AcceptProposalIn = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> CoachProposalsView:
    try:
        service.accept(db, user, fingerprint, body.revision, body.from_category_id)
    except service.CoachError as error:
        raise _fail(error) from error
    return list_proposals(db, user)
