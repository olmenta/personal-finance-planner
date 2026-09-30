# Design — AI Onboarding Interview

## Context

project-definition §6.6 fixed the architecture long before this change: the interview is driven by a **configurable, versioned prompt** (questions live in config, not code), extracted answers persist as one JSONB document per user (`UserPreferences`, accessed through a `PreferencesStore` interface), and the raw transcript lands in `OnboardingSession`. The data model section already names both tables; neither exists in `models.py` yet.

What exists today:

- `backend/app/services/category_suggestions.py` — the house LLM pattern: LiteLLM, pydantic `response_format`, id validation, provider-as-config.
- `backend/app/seed.py` — dev user + default Spanish category tree, explicitly a "stand-in until AI onboarding generates personalized trees". `current_user` (`deps.py`) resolves the seeded dev user; Auth0 comes later without touching query logic.
- Categories API with create/rename/archive; payees born from transaction writes with case-insensitive reuse (`services/payees.py`).
- Income is **derived** from confirmed positive transactions per month (`budget_view.income_cents`) — there is no stored income field. The 2026-06-10 decisions: income amount and `income_day` are captured by the interview and live in preferences.
- Coach UI primitives (`CoachMessage`, `CoachCapsule`, `CoachSuggestion`); prior decision: coach v1 has no free-form chat — these components are the skin for this interview.
- BFF: every browser call goes through a Next.js route handler using `proxyFetch` (`lib/server/backend.ts`).

The interview content is the user-supplied five-phase YNAB-style questionnaire (household/income, housing/utilities, true expenses, lifestyle/subscriptions, debt), extended with the income-amount and pay-day questions the original framework lacked.

## Goals / Non-Goals

**Goals:**

- A new user completes the interview in under ~2 minutes and lands in the app with a personalized category tree, starter payees/payers, and persisted preferences.
- Changing the interview (wording, question order, extra fields) means editing the prompt config + extraction schema, no backend code change.
- Every answer that informs category generation, import suggestions, or future coach features is captured in the preferences document.
- The user reviews and edits everything before anything is written — nothing is silently created.
- Abandon-and-resume works across page reloads.

**Non-Goals:**

- Auth0 / real multi-user (dev user only; the session row already keys by `user_id` so nothing changes later).
- Spanish copy via next-intl (English placeholders; the prompt takes a locale parameter).
- Budget amount suggestions per category, goals, or projections.
- Re-running or editing the interview after finalize (category CRUD covers post-hoc changes).
- Free-form coach chat beyond the interview.

## Decisions

### D1 — LLM-driven turn loop with the script in a versioned prompt config

Each turn is one LiteLLM structured-output call. The system prompt is `backend/app/prompts/onboarding_v1.md` (markdown with a YAML front-matter block declaring `version` and the extraction-field schema). The model receives the transcript so far and returns:

```python
class InterviewTurn(BaseModel):
    message: str                       # assistant bubble text
    input_kind: Literal["chips", "checkboxes", "text", "money"]
    options: list[str] = []            # for chips/checkboxes
    extracted: dict | None             # partial preferences delta, validated against schema
    done: bool = False
    proposal: SetupProposal | None     # only when done
```

*Why not a frontend state machine with fixed questions?* Cheaper and deterministic, but it re-hard-codes the questions §6.6 explicitly forbids hard-coding, and it cannot handle free-text answers like "my flat is fully electric". *Why not one mega-call asking everything at once?* Breaks the conversational promise and loses branching (vehicle count, copays follow-up).

Quick-input hints keep the <2-minute target: most turns are taps (chips/checkboxes), free text stays available. ~10–14 model calls per onboarding is acceptable for a once-per-user flow.

### D2 — Extraction schema covers the full questionnaire, not the thin sample JSON

The preferences document stores every answer the questionnaire collects (the framework's sample JSON omitted utilities, subscriptions, leisure, debt types, and income — all needed downstream). Shape (prompt-config-declared, validated server-side):

```json
{
  "household": {"management_style": "individual|joint", "children": false, "pets": []},
  "income": {"sources": ["..."], "expected_monthly_cents": 0, "income_day": 27},
  "housing": {"status": "rent|mortgage|owned", "utilities": ["electricity", "..."]},
  "transportation": {"owns_vehicles": true, "vehicle_count": 1},
  "healthcare": {"type": "public|private", "has_copays": true, "wants_copay_buffer": true},
  "subscriptions": ["Netflix", "..."],
  "leisure_priorities": ["dining_out", "..."],
  "savings_goals": ["travel", "..."],
  "debt": {"has_active_debt": true, "types": ["credit_card", "..."]}
}
```

`income_day` and `expected_monthly_cents` implement the 2026-06-10 decisions; month boundaries stay calendar months. Income is **not** written to any budget table — `income_cents` stays transaction-derived; preferences feed the coach and future suggestions.

### D3 — Two new tables, no changes to existing ones

```
OnboardingSession(id, user_id FK, prompt_version, status[active|completed|abandoned],
                  transcript_json, extracted_json, proposal_json, created_at, completed_at)
UserPreferences  (id, user_id FK unique, preferences JSONB, prompt_version, updated_at)
```

One Alembic migration. `UserPreferences` is read/written only through a `PreferencesStore` class (§6.6) so storage can move later. Transcript turns append on every exchange — resume is a `GET` of the active session; no in-memory state.

### D4 — Finalize is one transactional endpoint, not N client calls

`POST /onboarding/{session_id}/finalize` takes the reviewed proposal (post-edit: checked items only, renames applied, user-added rows included) and in a single transaction:

1. Creates category groups and categories, **reusing existing names case-insensitively** (the dev seed tree already exists; collisions reuse rather than 409 — mirrors payee resolve semantics rather than the public categories API).
2. Seeds accepted payees/payers via the existing `services/payees.py` resolve logic (payees spec amended to allow this; payers and payees are one entity, direction is presentation).
3. Persists `UserPreferences` and marks the session `completed`.

*Why not drive the public `POST /categories` endpoints from the client?* Partial failure would strand the user half-set-up; the review screen's "Add new" rows would need separate orchestration; and duplicate-name 409s against the seeded tree would surface as user-facing errors.

### D5 — Fail closed with a deterministic template fallback

Unlike import suggestions (fail-open to null), the interview *is* the feature. When `ANTHROPIC_API_KEY` is absent or a turn call fails after retry, the endpoint returns `503 onboarding_unavailable` with a flag the webapp turns into: "Set up with the starter template instead". That path finalizes with the default Spanish tree (already in `seed.py`, extracted to shared config) and empty preferences. No silent degradation mid-interview.

### D6 — Webapp: full-screen route outside the app shell, coach-skinned

`webapp/src/app/onboarding/page.tsx` (not under `(app)/` — no sidebar/nav, single-purpose screen). Chat composed from `CoachMessage` + chip/checkbox quick inputs; review screen is a two-section checklist (categories tree, payers/payees) with rename-in-place and "Add new" per section, then finalize → redirect to dashboard. Server state via the existing fetch-helper pattern in `lib/api.ts` and BFF handlers `app/api/onboarding/{start,messages,session,finalize}/route.ts` using `proxyFetch`.

Entry gating (does the app push you to `/onboarding` when no completed session exists?) stays manual for v1: dashboard shows a dismissible "Finish setting up" capsule linking to it. Hard gating belongs with Auth0 signup flow.

## Risks / Trade-offs

- [Per-turn latency makes the chat feel slow] → small `max_tokens`, no history re-summarization (transcript is short), typing indicator in UI; chips minimize round-trips.
- [Model drifts off-script or invents fields] → extraction delta validated against the prompt-declared schema server-side; unknown keys dropped and logged; `done` without a valid proposal re-prompts once then surfaces the fallback.
- [Proposal hallucination (weird categories)] → user reviews everything before persist; finalize validates shape, lengths, and dedupes case-insensitively.
- [Transcript contains personal lifestyle data] → same data-processor posture as imports (§6.2); transcript stored for prompt improvement per §6.6, deletable with the account; never logged.
- [Seeded dev tree muddies "new user" testing] → finalize's case-insensitive reuse makes re-runs idempotent in dev; tests build empty users directly.
- [Prompt config v2 changes field meanings] → `prompt_version` stored on both session and preferences; consumers read versioned documents.

## Migration Plan

1. Alembic migration adds both tables (additive, no rollback hazard).
2. Backend ships endpoints + prompt config; feature reachable only via `/onboarding` URL and the dashboard capsule.
3. Rollback = drop the route handlers/capsule; tables are inert.

## Open Questions

- None blocking. Account creation during onboarding was considered and deferred — the seeded default account covers v1; revisit with Auth0 signup.
