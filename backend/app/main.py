"""Personal Finance Planner API — entry point.

Run locally with:
    uv run uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from .routers import budget, categories, transactions

app = FastAPI(title="Personal Finance Planner API")

app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(budget.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
