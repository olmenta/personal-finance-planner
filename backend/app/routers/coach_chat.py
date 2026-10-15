"""The Home conversation and the coach's actions (spec: coach-conversation).

Refusals that record state (a stale preview, the kept user message of a
failed reply) are returned as responses, not raised, so the request's
transaction still commits them.
"""

from fastapi import APIRouter, Body, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import CoachAction, User
from ..schemas import (
    CoachActionIn,
    CoachActionOut,
    CoachCommitIn,
    CoachCommitOut,
    CoachConversationView,
    CoachSendIn,
    CoachSendOut,
)
from ..services import coach_actions as actions
from ..services import coach_chat as chat

router = APIRouter(prefix="/coach", tags=["coach"])

STATUSES = {"proposed", "applied", "stale", "cancelled", "undone"}


def _refused(error: actions.ActionError, db: Session, user: User) -> JSONResponse:
    detail = {"code": error.code, **{k: v for k, v in error.extra.items() if k != "action_id"}}
    if "action_id" in error.extra:
        detail["action"] = actions.action_out(db, user, actions.get_action(db, user, error.extra["action_id"]))
    return JSONResponse(status_code=error.status, content=jsonable_encoder({"detail": detail}))


@router.get("/conversation", response_model=CoachConversationView)
def get_conversation(
    before: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=chat.PAGE_SIZE, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    messages, has_more = chat.page(db, user, before, limit)
    return {"messages": chat.messages_out(db, user, messages), "has_more": has_more}


@router.post("/messages", response_model=CoachSendOut, responses={503: {"description": "coach_unavailable"}})
def send_message(
    body: CoachSendIn = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    try:
        user_message, reply = chat.send(db, user, body.text, body.client_message_id)
    except chat.CoachUnavailable:
        kept = db.scalar(select(chat.CoachMessage).where(
            chat.CoachMessage.user_id == user.id,
            chat.CoachMessage.client_message_id == body.client_message_id,
        ))
        detail = {"code": "coach_unavailable",
                  "user_message": chat.messages_out(db, user, [kept])[0] if kept else None}
        return JSONResponse(status_code=503, content=jsonable_encoder({"detail": detail}))
    user_out, reply_out = chat.messages_out(db, user, [user_message, reply])
    return {"user_message": user_out, "reply": reply_out}


@router.get("/actions", response_model=list[CoachActionOut])
def list_actions(
    status: str = Query(default="applied,undone"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[dict]:
    wanted = [s for s in status.split(",") if s in STATUSES]
    rows = db.scalars(
        select(CoachAction)
        .where(CoachAction.user_id == user.id, CoachAction.status.in_(wanted))
        .order_by(CoachAction.applied_at.desc().nulls_last(), CoachAction.created_at.desc())
        .limit(100)
    )
    return [actions.action_out(db, user, a) for a in rows]


@router.post("/actions", response_model=CoachActionOut, status_code=201)
def create_action(
    body: CoachActionIn = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Review a change from a widget, or edit a proposed one: a new preview,
    nothing applied."""
    try:
        command = actions.command_from_input(db, user, body)
        if body.replaces:
            old = actions.get_action(db, user, body.replaces, lock=True)
            action = actions.replace(db, user, old, command)
        else:
            action = actions.propose(db, user, command)
    except actions.ActionError as error:
        return _refused(error, db, user)
    return actions.action_out(db, user, action)


@router.post("/actions/{action_id}/commit", response_model=CoachCommitOut)
def commit_action(
    action_id: str,
    body: CoachCommitIn = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    try:
        action = actions.commit(db, user, action_id, body.revision, body.idempotency_key)
    except actions.ActionError as error:
        return _refused(error, db, user)
    message = chat.record_result(db, user, action)
    return {"action": actions.action_out(db, user, action), "message": chat.messages_out(db, user, [message])[0]}


@router.post("/actions/{action_id}/cancel", response_model=CoachActionOut)
def cancel_action(action_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        action = actions.cancel(db, user, action_id)
    except actions.ActionError as error:
        return _refused(error, db, user)
    return actions.action_out(db, user, action)


@router.post("/actions/{action_id}/undo", response_model=CoachActionOut)
def undo_action(action_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        action = actions.undo(db, user, action_id)
    except actions.ActionError as error:
        return _refused(error, db, user)
    return actions.action_out(db, user, action)
