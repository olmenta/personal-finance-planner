"""Personal Finance Planner API — entry point.

Run locally with:
    uv run uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from .routers import (
    accounts,
    budget,
    debts,
    categories,
    imports,
    income,
    onboarding,
    payees,
    plan,
    schedules,
    summary,
    transactions,
    transfers,
)
from .llm.observability import configure_logfire
from .telemetry import configure_sentry

configure_sentry()

app = FastAPI(title="Personal Finance Planner API")
# After the app exists: FastAPI instrumentation needs it. Dormant without a token.
configure_logfire(app)

app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(schedules.router)
app.include_router(payees.router)
app.include_router(transactions.router)
app.include_router(transfers.router)
app.include_router(imports.router)
app.include_router(budget.router)
app.include_router(summary.router)
app.include_router(onboarding.router)
app.include_router(plan.router)
app.include_router(income.router)
app.include_router(debts.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}