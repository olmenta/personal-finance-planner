"""Personal Finance Planner API — entry point.

Run locally with:
    uv run uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from .routers import (
    budget,
    categories,
    imports,
    onboarding,
    payees,
    plan,
    schedules,
    summary,
    transactions,
)
from .telemetry import configure_sentry

configure_sentry()

app = FastAPI(title="Personal Finance Planner API")

app.include_router(categories.router)
app.include_router(schedules.router)
app.include_router(payees.router)
app.include_router(transactions.router)
app.include_router(imports.router)
app.include_router(budget.router)
app.include_router(summary.router)
app.include_router(onboarding.router)
app.include_router(plan.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}