"""Month summary for the dashboard: balance, totals, weekly buckets."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import SummaryView
from ..services import summary

router = APIRouter(prefix="/summary", tags=["summary"])

MONTH = Path(pattern=r"^\d{4}-\d{2}$")


@router.get("/{month}", response_model=SummaryView)
def get_summary(
    month: str = MONTH,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SummaryView:
    return summary.build_summary(db, user, month)
