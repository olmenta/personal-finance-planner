"""Month overview, upcoming payments and annual plan
(specs: month-overview, payment-projection). Expected income lives in
income schedules (routers/income.py)."""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import OverviewView, PlanSummary, UpcomingView
from ..services import projection
from ..services.overview import build_overview

router = APIRouter(tags=["plan"])

MONTH_RE = r"^\d{4}-(0[1-9]|1[0-2])$"


@router.get("/overview/{month}", response_model=OverviewView)
def get_overview(
    month: str = Path(pattern=MONTH_RE),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> OverviewView:
    return build_overview(db, user, month)


@router.get("/plan/upcoming", response_model=UpcomingView)
def get_upcoming(
    from_: str = Query(alias="from", pattern=MONTH_RE),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> UpcomingView:
    return projection.upcoming(db, user, from_)


@router.get("/plan/summary", response_model=PlanSummary)
def get_summary(
    from_: str = Query(alias="from", pattern=MONTH_RE),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> PlanSummary:
    return projection.summary(db, user, from_)
