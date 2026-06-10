# Olmenta — Personal Finance Planner

Subscription web app that teaches first-time budgeters simplified zero-based budgeting, with an AI coach removing the onboarding friction. See [project-definition.md](project-definition.md) for the full product scope and [CLAUDE.md](CLAUDE.md) for conventions.

## Local development

The webapp talks to the Python API only through Next.js Route Handlers (BFF), so local dev runs **two processes**:

**1. Backend** (FastAPI on `:8000`):

```sh
cd backend
uv sync
uv run python -m app.seed   # first run: dev user + default category tree
uv run uvicorn app.main:app --reload
```

**2. Webapp** (Next.js on `:3000`):

```sh
cd webapp
volta run npm install
volta run npm run dev
```

The BFF resolves the backend via `BACKEND_URL` (defaults to `http://localhost:8000`; see [webapp/.env.example](webapp/.env.example)). If the backend isn't running, screens show a retryable error state with code `backend_unavailable`.

## Tests

```sh
cd backend && uv run pytest        # needs TEST_DATABASE_URL (see backend/.env.example)
cd webapp && volta run npm run lint && volta run npm run build
```
