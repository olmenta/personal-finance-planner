"""Coach proposals: list, dismiss for a week, accept a raise or lower
(spec: coach-proposals)."""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import AcceptProposalIn, CoachProposalOut, CoachProposalsView
from ..services import coach as service

router = APIRouter(prefix="/coach", tags=["coach"])


def _out(p: service.Proposal) -> CoachProposalOut:
    data = p.payload
    return CoachProposalOut(
        fingerprint=p.fingerprint,
        kind=p.kind,  # type: ignore[arg-type]
        title=p.title,
        body=p.body,
        action=p.action,  # type: ignore[arg-type]
        amount_cents=p.amount_cents,
        category_id=data.get("category_id"),
        current_cents=data.get("current_cents"),
        suggested_cents=data.get("suggested_cents"),
        diff_cents=data.get("diff_cents"),
        sources=data.get("sources"),
        schedule_id=data.get("schedule_id"),
        payer=data.get("payer"),
        href=data.get("href"),
    )


def _fail(error: service.CoachError) -> HTTPException:
    return HTTPException(status_code=error.status, detail={"code": error.code})


@router.get("/proposals", response_model=CoachProposalsView)
def list_proposals(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> CoachProposalsView:
    proposals = service.visible(db, user)
    return CoachProposalsView(proposals=[_out(p) for p in proposals], total=len(proposals))


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
    body: AcceptProposalIn = Body(default=AcceptProposalIn()),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> CoachProposalsView:
    try:
        service.accept(db, user, fingerprint, body.from_category_id)
    except service.CoachError as error:
        raise _fail(error) from error
    return list_proposals(db, user)
