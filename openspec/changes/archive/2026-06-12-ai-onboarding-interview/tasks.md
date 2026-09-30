# Tasks — AI Onboarding Interview

## 1. Data layer

- [x] 1.1 Add `OnboardingSession` and `UserPreferences` models to `backend/app/models.py` (per design D3)
- [x] 1.2 Alembic migration creating both tables (`uv run alembic revision --autogenerate` + review)
- [x] 1.3 `PreferencesStore` class in `backend/app/services/preferences.py` (get/put document with prompt version, JSONB column access only through it)

## 2. Prompt configuration

- [x] 2.1 Create `backend/app/prompts/onboarding_v1.md`: YAML front matter (`version`, extraction-field schema per design D2) + interview script covering the five phases, income amount + `income_day` question, tone, and turn-output contract
- [x] 2.2 Loader in the onboarding service: parse front matter, expose `prompt_version`, build the per-turn system prompt with locale parameter; validate extraction deltas against the declared schema (drop + log unknown keys)

## 3. Interview engine (backend)

- [x] 3.1 Pydantic turn models (`InterviewTurn`, `SetupProposal` with groups/categories/payers/payees/income) in `backend/app/services/onboarding.py`, LiteLLM structured-output call following the `category_suggestions.py` pattern (provider via config, never SDKs)
- [x] 3.2 Session lifecycle: start (idempotent on active session), append turns to `transcript_json`, merge validated extraction deltas into `extracted_json`, store proposal on `done`; re-ask once on `done` without valid proposal
- [x] 3.3 Router `backend/app/routers/onboarding.py`: `POST /onboarding/start`, `GET /onboarding/session` (404 `no_active_session`), `POST /onboarding/messages`, all behind `current_user`; 503 `onboarding_unavailable` when key missing or call fails after retry; no transcript content in logs
- [x] 3.4 Register router in `app/main.py`

## 4. Finalize

- [x] 4.1 Extract the default starter tree from `seed.py` into shared config usable by both seed and the template-fallback finalize
- [x] 4.2 `POST /onboarding/{session_id}/finalize`: single transaction — create groups/categories with case-insensitive reuse, seed accepted payees via `services/payees.py` resolution, persist preferences through `PreferencesStore`, mark session `completed`; 409 `session_not_active`; template-fallback variant (default tree, no preferences)

## 5. Backend tests

- [x] 5.1 Session lifecycle tests: start idempotency, resume returns transcript, 404 without session
- [x] 5.2 Turn tests with mocked LiteLLM: quick-input hints pass through, unknown extraction keys dropped, free-text answer merges, `done` stores proposal, retry-then-503 path
- [x] 5.3 Finalize tests: reviewed payload created exactly (uncheck/rename/add-new), case-insensitive group reuse against seeded tree, payee seeding, atomic rollback on failure, 409 on completed session, template fallback
- [x] 5.4 Preferences tests: one document per user, prompt version recorded, income fields present, no budget-table income writes

## 6. BFF + API client

- [x] 6.1 Route handlers `webapp/src/app/api/onboarding/{start,session,messages,[id]/finalize}/route.ts` via `proxyFetch`, status/error pass-through (plus `template/route.ts` for the fallback)
- [x] 6.2 `lib/api.ts`: typed client functions + TypeScript interfaces for turn, proposal, finalize payload

## 7. Onboarding UI

- [x] 7.1 `/onboarding` full-screen route outside `(app)/`: chat column from coach primitives (`CoachMessage`), assistant typing indicator, chips/checkboxes/money quick inputs + free-text input, resume from `GET /api/onboarding/session` on load
- [x] 7.2 Review screen: category checklist grouped by group, payers and payees sections — uncheck, rename in place, "Add new" per section — building the finalize payload
- [x] 7.3 Finalize call + redirect to dashboard; 503 path renders "Use the starter template instead" flow
- [x] 7.4 Dashboard: dismissible "finish setting up" coach capsule linking to `/onboarding` while no completed session exists (backed by new `GET /onboarding/status`)

## 8. Verification

- [x] 8.1 `uv run pytest` green in `backend/` (135 + 1 new status test)
- [x] 8.2 `volta run npm run build` and `volta run npm run lint` green in `webapp/`
- [x] 8.3 Manual walkthrough with a real API key: full interview ≤ ~2 min via taps, review edits applied exactly, payees visible in `GET /payees`, preferences row written (completed 2026-06-12: 27-turn interview finalized in browser — 9 groups, 36 categories, payees seeded, preferences document written)
