# AI Onboarding Interview

## Why

New users face a blank slate: an empty category tree (the seeded Spanish defaults are an explicit stand-in), no payees, and no recorded income — the exact onboarding friction Olmenta exists to remove (project-definition §2.1, §6.6). The activation metric (complete AI onboarding + first budget within 48h) has no feature behind it yet. This change ships the conversational onboarding interview: a YNAB-style "true expenses" questionnaire delivered as an AI chat, ending in a review-and-confirm screen that creates the user's personalized category tree, starter payees/payers, and income preferences.

## What Changes

- New full-screen onboarding chat at `/onboarding` (coach-skinned, no app shell) that walks the user through a five-phase YNAB-style interview: household & income, housing & utilities, true expenses (vehicles, healthcare, dependents), lifestyle & subscriptions, and debt — plus income amount and pay day (decisions of 2026-06-10: income arrives via the interview; `income_day` feeds future coach guidance).
- Interview is driven by a **versioned prompt configuration** (repo file), not hard-coded questions (project-definition §6.6): each turn is one LiteLLM structured-output call returning the assistant message, a quick-input hint (chips / checkboxes / free text / money), and incrementally extracted answers.
- New backend capability: onboarding session lifecycle (start, message turns, resume, finalize) with two new tables — `OnboardingSession` (transcript, prompt version, generated proposal) and `UserPreferences` (per-user JSONB preferences memory behind a `PreferencesStore` interface).
- Interview completion produces a **generated setup proposal** (category groups → categories, payers, payees, income summary) that the webapp renders as an editable checklist (uncheck, rename, add new) before anything is persisted.
- Finalize applies the reviewed proposal in one transaction: create category groups/categories (reusing existing names case-insensitively), seed accepted payees/payers, persist preferences + transcript.
- Fail-closed UX with deterministic fallback: when no LLM key is configured or the model call fails repeatedly, the user is offered the default starter template instead of the interview (interview is the feature; silent degradation is not acceptable here, unlike import suggestions).
- BFF route handlers under `webapp/src/app/api/onboarding/*` proxy all calls; the browser never reaches the Python API.

## Capabilities

### New Capabilities

- `ai-onboarding`: the onboarding interview contract — session lifecycle (start/resume/turns/finalize), prompt-config versioning, extraction schema persisted to the per-user preferences memory, generated setup proposal shape, fallback behavior, and what finalize creates.

### Modified Capabilities

- `payees`: "no separate payee-creation path" requirement amended — onboarding finalize MAY seed payees/payers the user accepted during review (still no public payee CRUD endpoint).
- `bff-proxy`: add the onboarding route handlers to the proxied surface.

## Impact

- **Backend**: new `app/routers/onboarding.py`, `app/services/onboarding.py` (+ prompt config file `app/prompts/onboarding_v1.*`), new models `OnboardingSession`, `UserPreferences`, one Alembic migration; reuses LiteLLM structured-output pattern from `category_suggestions.py` and payee resolve logic from `services/payees.py`.
- **Webapp**: new route `webapp/src/app/onboarding/` (outside the `(app)` shell), chat UI composed from Coach primitives (`CoachMessage`, `CoachCapsule`), review checklist screen, BFF handlers `app/api/onboarding/*`, API client additions in `lib/api.ts`.
- **Data**: two new tables; no changes to existing tables. Income stays derived from transactions — interview income lands in `UserPreferences` only.
- **Config**: reuses `ANTHROPIC_API_KEY`; model name via existing settings.
- **Out of scope**: Auth0 (interview runs against the seeded dev user via `current_user`), Spanish i18n strings (English placeholder copy, prompt locale-parameterized), budget amount suggestions per category, re-running the interview after completion (categories stay editable via existing CRUD).
