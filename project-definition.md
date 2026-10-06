# Project Definition — Personal Finance App (Working Title)
 
**Version:** 0.2 (Draft)
**Date:** June 2026
**Status:** Pre-development — foundation document for the repository
 
---
 
## 1. Vision
 
A subscription-based web application that helps people who have never budgeted before take control of their money using a simplified zero-based budgeting method (YNAB-style), where AI removes the friction that makes traditional budgeting apps fail for beginners.
 
The product's core promise: **"Know where your money goes each month, and know what your upcoming months will cost you — without becoming a spreadsheet expert."**
 
## 2. Target User & Problem
 
**Target user:** People who have never made a budget, who have tried and abandoned complex finance apps, and who never know how much their expenses will be in the coming months nor where their money goes month to month.
 
**Problem statement:** Existing budgeting tools either demand too much manual discipline (zero-based tools like YNAB have a steep learning curve) or provide passive dashboards that don't change behavior (bank aggregators). Beginners abandon both.
 
**Our bet:** Zero-based budgeting works — the learning curve is the problem, not the method. We attack the learning curve with:
 
1. **AI-assisted onboarding** — a short conversational interview (housing, vehicles, children, pets, subscriptions...) that generates a personalized category tree, instead of presenting the user with a blank slate. Example: if the user owns two cars, the assistant suggests fuel, insurance, maintenance, and inspection categories automatically.
2. **Suggested monthly assignments** — each new month, the app proposes the budget allocation based on the previous month's data. Assigning every euro should feel like *confirming suggestions*, not filling in a blank spreadsheet.
3. **Low-friction capture** — registering an expense takes under 5 seconds; bank CSV import covers the rest.
## 3. Budgeting Method

**Zero-based budgeting, YNAB-style** (every euro of income gets a job), simplified for beginners: the method stays, the app does the math. Revised 2026-10-04 from a review of a real household budget; each principle below is specified in `openspec/specs/` and the change that introduced it is archived with its rationale.

### 3.1 Principles

1. **Only budget money you already have.** Income enters *To Be Assigned* when it arrives. Expected income is planned (income schedules) and matched against what actually arrives (received, a little less or more, late, missed), but it is never assigned before it lands. Probable money (bonuses that depend on company targets) is never part of the plan; when it lands, it is assigned like any other income.
2. **Every euro has a job, and unassigned money carries over.** The goal is To Be Assigned = 0, but money left unassigned at month end passes to the next month instead of disappearing. This is what lets a salary paid on the 27th fund the next month ("age your money").
3. **Calendar months, Europe/Madrid.** The budget period is never tied to payday; with several incomes there is no single start date. Carry-over (principle 2) makes calendar months work.
4. **The budget is not the payment calendar.**
   - Every cost is budgeted as its monthly amount: annual cost ÷ 12. School fees of 632 € from September to June cost 526,67 € every month, July and August included.
   - When money actually leaves is a separate calendar, described once per payment with a rule: every month, some months, once a year, every N months, or once on a date.
   - **The app always computes the monthly amount.** A category with payments is assigned exactly that amount and the user never types it.
5. **Catch up when behind.** If what's saved isn't enough for the payments ahead, the monthly amount becomes the *catch-up amount*: the minimum to set aside each month so no payment goes uncovered. It drops back to normal by itself once the user is on track. A future expense, even years away, is spread over every month until it; that is how savings for a goal work.
6. **Coverage of future payments is always visible.** The home screen shows what to solve now: paid, still to pay (covered or short), left to spend. A 12-month projection shows, months ahead, any payment that won't be covered.
7. **One annual plan.** Expected fixed income for 12 months versus planned costs (payments + day-to-day + goals) gives one honest number: the yearly and monthly gap. Expected income is described per source with the same rules as payments (every month, some months, …), so 14 pagas (extra pays in June and December), several incomes and different paydays project month by month; income still due this month carries into the next. When the plan doesn't fit, it is adjusted, not ignored.
8. **Roll with the punches: cover overspending in the month it happens.**
   - When a category goes over, the money already left the bank, so it is covered right away by moving money from another category. The app suggests the source in one tap and never blocks expense entry.
   - Only if the month closes uncovered is the amount deducted from next month's To Be Assigned, and the category starts clean (never a negative carry-over).
   - If a category overspends month after month, the coach proposes raising its budget.
9. **Refunds return to their category.** An inflow with a category is a refund: it lowers that category's spending and never counts as income.
10. **Credit cards the YNAB way** (planned with accounts and transfers).
    - A card purchase is spending in its category at purchase time.
    - The budgeted amount moves automatically to the card's payment category.
    - Paying the card is a transfer, not an expense.
    - Overspending on credit becomes card debt.
    - Pre-existing card debt doesn't reduce To Be Assigned; it is shown as uncovered debt.
11. **Pay debts in order, without jargon.** Cards (the old balance), loans with installments and money owed to people are debts.
    - Their required payments (a card's monthly plan, each installment, a personal debt with a date) are payment schedules: inside the budget, with a nudge when one is late.
    - Extra money is optional and goes to one debt at a time: the highest known interest first, then unknown, then interest-free; when one is done, its money moves to the next.
    - The interest rate is optional and only orders debts and says "~X €/month just for owing it". Never TAE, APR or amortization.
12. **Money in the accounts always adds up.**
    - Money in the accounts = To Be Assigned + everything set aside in categories.
    - The home screen splits that money into: to pay this month, left to spend, saved for the future, and unassigned.

### 3.2 Category kinds

| Kind | How it's set | Assignment |
|---|---|---|
| **With payments** (rent, school, insurance, utilities) | Automatically, by having at least one payment | Computed from its payments; read-only |
| **Day-to-day** (groceries, restaurants, fuel) | Default | Typed by the user; suggested from the previous month |
| **Savings** (children's savings, emergency fund) | A "Savings" switch on the category | Typed by the user; shown as saved, never as spendable |

Each payment has its own rule; one category can hold several (school fee monthly from September to June, books once a year in September).

### 3.3 Home-screen questions

The app always answers: *"What do I have to solve this month?"* (paid, still to pay, left to spend), *"Did my income arrive?"* (expected versus received, with a nudge when it's late), *"Where is the rest of my money?"* (saved for the future, unassigned), and *"Will my next months be covered?"* (upcoming payments and the annual gap).

## 4. Scope
 
### 4.1 MVP Features (v1)
 
| # | Feature | Description |
|---|---------|-------------|
| 1 | Expense/income entry | Manual entry optimized for mobile; < 5 seconds per transaction. Amount, category, optional note and date (defaults to today). |
| 2 | Categories + AI onboarding | Conversational onboarding interview driven by a **configurable prompt** (questions are not hard-coded). The interview extracts specific answers we want to persist into a per-user **preferences memory** (see §6.6), then generates a personalized category tree. Categories editable afterwards (create, rename, archive, group). |
| 3 | Zero-based budget per category | Monthly assignment of every euro (§3). Categories with payments assigned their computed monthly amount; day-to-day categories suggested from the previous month. Rollover of unspent balances, To Be Assigned carry-over, one-tap overspending cover and money moves between categories. |
| 4 | CSV import | Import bank statements from **BBVA Spain** and **Sabadell Spain** CSV exports. Pipeline: parse → normalize → deduplicate → AI category suggestion → user confirmation. |
| 5 | Monthly summary & plan | Home screen "this month" (paid / to pay / left to spend / saved / unassigned, adding up to the accounts). Payment schedules per category with computed monthly amounts. Income schedules per source (14 pagas, several incomes) matched against received income. 12-month upcoming-payments projection with coverage and the annual plan gap against expected fixed income. |
| 6 | Simple chart | Spending distribution for the current month + spending evolution over time. |
 
**Cross-cutting (v1):** authentication (Auth0), subscription billing (Stripe: configurable trial + 5 €/month plan), responsive web UI, **Spanish-only launch with i18n-ready architecture** (see §6.7), GDPR-compliant data handling.
 
### 4.2 Deferred ("Later" list)
 
- Multi-currency support (a card billed in another currency is recorded in euros)
- Multiple budgets per user (e.g. separating personal projects' costs from the household budget)
- Chat about debts: a short coach interview, opened from the always-visible "Work on my debts" button, to add or re-plan debts by talking
- Coach proposals on the plan (repeated overspending, monthly plan adjustments) and onboarding extraction of payment schedules
- Advanced reports
- Reminders / notifications
- **Expense capture via WhatsApp (AI)** — on roadmap
- **Receipt OCR** — on roadmap
- **Automatic bank connections (Open Banking / PSD2)** via aggregation providers (e.g. GoCardless, Tink) — on roadmap; architecture must be ready for this from day one (see §6.3)
### 4.3 Explicit Non-Goals (v1)
 
- No investment tracking, no net-worth dashboards, no crypto.
- No native mobile apps (responsive web only).
- No shared/multi-user budgets.
- No direct bank connections in v1 (CSV only).
## 5. Roadmap
 
| Phase | Contents |
|-------|----------|
| **v1 (MVP)** | The 6 features above + Auth0 + Stripe + CSV import (BBVA, Sabadell) |
| **v1.x** | More Spanish banks' CSV formats; improved projections; budget templates |
| **v2** | WhatsApp expense capture (AI), receipt OCR, reminders, savings goals |
| **v3** | Open Banking connections via aggregator(s); multi-currency; advanced reports |
 
## 6. Architecture
 
### 6.1 High-Level Design
 
```
Browser (Next.js app)
   │  (same-origin HTTPS)
   ▼
Next.js Route Handlers — BFF layer (Vercel)
   │  validates Auth0 session, attaches JWT, proxies requests
   ▼
Python API — FastAPI on Google Cloud Run
   │  stateless; validates Auth0 JWT (signature + claims)
   ├── Neon (serverless PostgreSQL)
   ├── Anthropic API (onboarding interview, category suggestions)
   ├── Stripe (billing; webhooks → Cloud Run endpoint)
   └── Cloud Tasks → async workers (CSV ingestion; later: OCR, bank webhooks)
```
 
**Key principles:**
 
- The browser never talks to the Python API directly. The Next.js BFF is the single public surface for the client: it hides the internal API, enforces sessions, and allows backend changes without touching the frontend.
- The Python backend is stateless. All session validation is JWT-based (Auth0), which fits Cloud Run's scale-to-zero model.
- Async-first for heavy work: CSV processing runs through Cloud Tasks workers. The same mechanism will later serve OCR jobs and Open Banking webhook processing.
### 6.2 Technology Stack
 
| Layer | Choice | Notes |
|-------|--------|-------|
| Frontend | **Next.js 15+ (App Router, TypeScript)** on Vercel | Tailwind CSS + shadcn/ui; TanStack Query for server state (optimistic updates for instant-feeling expense entry) |
| BFF | Next.js Route Handlers | Session validation, request proxying, feature gating by subscription status |
| Auth | **Auth0** | Universal Login on the frontend; Python validates RS256 JWTs against Auth0 JWKS. Roles/entitlements in custom claims. |
| Backend | **Python + FastAPI** on **Google Cloud Run** | Pydantic validation, auto-generated OpenAPI. Scale to zero; identical local/prod environment (containers). |
| Database | **Neon (serverless PostgreSQL)** | SQLAlchemy 2.0 + Alembic migrations. Neon branching for per-environment / per-PR databases. |
| Async jobs | Google Cloud Tasks + Cloud Run worker service | CSV ingestion pipeline; future OCR and webhook processing |
| Billing | **Stripe** | Checkout + Billing + Customer Portal. Webhooks handled by the Python API; subscription state mirrored in Neon. |
| AI | **Anthropic API** (called from Python only) | Onboarding interview driven by a configurable, versioned prompt (see §6.6) → structured JSON answers + category tree; transaction category suggestions |
| Object storage | **Google Cloud Storage** | Temporary CSV upload storage (raw files, deleted after retention window) |
| IaC | **Terraform** | All GCP resources (Cloud Run services, Cloud Tasks, service accounts, secrets), Neon (via provider), Auth0 (via provider) |
| Observability | Sentry (frontend + backend), Cloud Run logs/metrics | |
| CI/CD | GitHub Actions | Lint, test, build, deploy. Terraform plan/apply via CI. |
| Repo | **Monorepo**: `webapp/` (Next.js), `backend/` (FastAPI), `mobile/` (Ionic — future release) | TypeScript API client auto-generated from FastAPI's OpenAPI spec — typed contract between BFF and backend |
 
**Toolchain conventions (mandatory):**
 
- **Backend (`backend/`):** The Python version is pinned with **uv** (`.python-version`, via `uv python pin`). Use **uv** for everything: installing libraries (`uv add <pkg>`), running scripts (`uv run <script>`), and serving the API with **uvicorn** (`uv run uvicorn app.main:app --reload`). Never call `pip` or a system Python directly.
- **Frontend (`webapp/`, later `mobile/`):** The Node version is pinned with **Volta** (`volta` field in `package.json`). Always go through Volta for installing libraries and running npm (`volta run npm install`, `volta run npm run dev`, …) — or rely on Volta's shims so `npm`/`node` resolve to the pinned version. Never use a system Node that bypasses the pin.
- **Mobile (`mobile/`, future):** Ionic app, planned for a later release; same Volta/Node conventions as `webapp/`.
 
### 6.3 Transaction Ingestion — Ports & Adapters
 
Designed so that adding Open Banking later requires **zero changes to the domain logic**.
 
- **Port (interface):** `TransactionSource` — returns transactions in a normalized contract: `date`, `amount` (signed, cents), `currency`, `description`, `external_ref` (for deduplication), `raw_payload`.
- **Adapters (v1):** `BBVACsvAdapter`, `SabadellCsvAdapter`.
- **Adapters (future):** `GoCardlessAdapter`, `TinkAdapter`, `WhatsAppAdapter`, `ReceiptOcrAdapter` — same port, same pipeline.
- **Common pipeline (adapter-agnostic):**
  1. Parse (adapter-specific)
  2. Normalize to the contract
  3. Deduplicate — hash of `(account, date, amount, external_ref/description)`
  4. AI category suggestion
  5. User review & confirmation (staged transactions are not budgeted until confirmed)
Every transaction stores its `source` (`manual`, `csv_bbva`, `csv_sabadell`, later `openbanking_*`, `whatsapp`, `ocr`) and the `ImportBatch` it came from, enabling per-source troubleshooting and batch rollback.
 
> ⚠️ **Known risk:** Spanish banks change CSV export formats without notice. Adapters must be defensive (header detection, format versioning) and covered by fixture-based tests with real anonymized samples. Budget double the apparent effort for this feature.
 
### 6.4 Initial Data Model
 
```
User            (id, auth0_sub, email, locale, created_at)
Subscription    (id, user_id, stripe_customer_id, stripe_subscription_id,
                 status, plan, current_period_end)
Account         (id, user_id, name, type[cash|bank], institution, created_at)
Category        (id, user_id, group_id, name, icon, archived)
CategoryGroup   (id, user_id, name, sort_order)
Transaction     (id, user_id, account_id, category_id?, date, amount_cents,
                 description, source, import_batch_id?, dedupe_hash,
                 status[staged|confirmed], created_at)
BudgetMonth     (id, user_id, month, to_be_assigned_cents)
BudgetAssignment(id, budget_month_id, category_id, assigned_cents)
ImportBatch     (id, user_id, account_id, source, filename, status,
                 row_count, created_at)
OnboardingSession(id, user_id, prompt_version, transcript_json,
                 extracted_answers_json, generated_categories_json,
                 completed_at)
UserPreferences (id, user_id [unique], preferences JSONB, prompt_version,
                 updated_at) — preferences memory, see §6.6
IncomeSchedule  (id, user_id, name, amount_cents, payee_id?, pattern + rule
                 fields, day?, estimated, created_at) — expected income;
                 feeds the plan, never the budget
Debt            (id, user_id, category_id [unique], kind[card|loan|personal],
                 rate_bp?, rate_period?, minimum_cents?, owed_cents?,
                 due_month?, payee_id?, created_at) — owed is derived per kind
DebtSettings    (user_id, extra_monthly_cents)
```
 
Notes:
- Amounts stored as integer cents; currency fixed to EUR in v1 (column present for future multi-currency).
- `dedupe_hash` has a unique constraint per account.
- Category available balance is derived: `assigned + rollover − spent` (computed, with a materialized monthly snapshot if performance requires it).
### 6.5 Security & Compliance
 
- GDPR: EU data residency (Neon EU region, Cloud Run `europe-*`), data export and account deletion endpoints from day one, minimal data collection.
- Secrets in GCP Secret Manager, injected via Terraform; never in code or CI variables.
- Auth0 JWT validation on every Python endpoint; BFF never forwards unauthenticated requests.
- CSV uploads: size limits, content-type validation, processed in isolated worker, raw files deleted after a retention window.
- Stripe webhook signature verification; idempotent webhook handlers.
### 6.6 AI Onboarding — Configurable Prompt & Preferences Memory
 
**Decision:** onboarding questions are **not hard-coded**. The interview is driven by a configurable prompt that defines both the questions to ask and the specific answer fields we want to extract and persist.
 
- **Onboarding prompt (configuration):** a versioned prompt template stored in the repo/config (not in code logic) that defines: the interview questions, the tone, and a schema of the answers to extract (e.g. `has_vehicles: bool`, `vehicle_count: int`, `housing_type: rent|mortgage|owned`, `has_children: bool`, `pets: list`, ...). Changing the interview means editing the prompt + extraction schema, with no backend code changes. Prompt versions are tracked so each user's preferences record which version produced it.
- **Preferences memory (per-user JSON document, v1):** the extracted answers are persisted as **one JSON document per user**, stored in a **`JSONB` column in Neon** (`UserPreferences` table). This keeps the data transactional alongside the rest of the user's data, queryable (e.g. "users with vehicles"), and covered by the same backup/branching story as everything else. Access goes through a `PreferencesStore` interface, so the storage backend can be swapped without touching consumers. The document stores: extracted answers, prompt version, timestamps, and free-form notes the AI may add.
- **Usage:** the preferences memory feeds (a) category tree generation at onboarding, (b) category suggestions during CSV import, and (c) future features (projections, WhatsApp capture context).
- The raw interview transcript is stored separately (`OnboardingSession`) for auditing and prompt improvement.
### 6.7 Internationalization
 
**Decision:** v1 launches in **Spanish only**, but the architecture is multilanguage-ready from day one:
 
- All UI strings via an i18n library (`next-intl`) with `es` as the only active locale; no hard-coded strings in components.
- `User.locale` already in the data model; dates, numbers and currency formatted through locale-aware utilities.
- AI prompts (onboarding, category suggestions) parameterized by locale.
- Backend error messages returned as machine-readable codes; the frontend maps codes to translated strings.
## 7. Business Model
 
- Subscription via Stripe at **5 €/month**.
- **Trial length configured in Stripe** (`trial_period_days` on the subscription/Checkout), so it can be changed without code deployments. Starting value to be set at launch (14 days suggested).
- Feature gating enforced in the BFF based on subscription status mirrored from Stripe webhooks.
- No free tier in v1 (trial only) — revisit after launch data. Annual plan deferred until after launch.
## 8. Success Metrics (v1)
 
- **Activation:** % of new users who complete AI onboarding and assign their first monthly budget within 48h.
- **Habit:** % of users who log ≥ 3 transactions per week (manual or import) in weeks 2–4.
- **Retention:** % of users who create a budget for their **second** month (the key abandonment cliff for zero-based tools).
- **Time-to-entry:** median time to register an expense (< 5 s target).
- **Conversion:** trial → paid rate.
## 9. Key Risks
 
| Risk | Mitigation |
|------|------------|
| Zero-based method too demanding for the target user | AI onboarding + auto-suggested monthly assignments; ruthless UX simplification; measure second-month retention from day one |
| Bank CSV formats change silently | Defensive adapters, format versioning, fixture tests, clear user-facing error messages |
| Cold starts on Cloud Run hurt perceived speed | Min instances = 1 for the API in production if needed; keep BFF responses cached where safe |
| AI category suggestions wrong → user distrust | Suggestions always require confirmation; learn from user corrections |
| Subscription-only model limits top of funnel | Trial generous enough to reach the "aha" moment (first full month budgeted) |
 
## 10. Decisions Log & Open Questions
 
**Resolved (v0.2):**
 
- **Language:** v1 launches in Spanish only, with multilanguage-ready architecture (§6.7).
- **Onboarding:** questions configurable via a versioned prompt; extracted answers persisted in a per-user preferences memory stored as a **`JSONB` document in Neon** (`UserPreferences` table), accessed through a `PreferencesStore` interface (§6.6).
- **Pricing:** 5 €/month; trial length configured in Stripe, changeable without deployments (§7).
**Resolved (v0.3, 2026-09-30 → 10-04 — budgeting method, §3):**

- Budget ≠ payment calendar; the app computes every monthly amount (normal and catch-up), and categories with payments are not typed by hand.
- Unassigned money carries over; calendar months (Europe/Madrid) stay — configurable periods rejected.
- Overspending: cover within the month; uncovered cash overspending is deducted from next month's To Be Assigned (no negative carry-over).
- Probable income (bonuses) is never budgeted; expected *fixed* income feeds the annual plan.
- Savings goals are future expenses (a payment on a date), not "have X by a date" targets.
- Credit cards follow YNAB (payment category, card debt); multi-currency stays out of v1.
- Debts (2026-10-07): card, installment loan or personal, each linked to the category that pays it; what's owed is derived (card balance minus what's set aside for new spending, installments left, amount minus payments). Required payments are payment schedules; the optional extra goes to the highest known interest first. A loan set up as a card is converted with "This is a loan, not a card". Chat capture of debts is the next step.
- Expected income is a list of income schedules (2026-10-06), not one monthly figure: same rules as payments, a payer that is a payee, matched to real income at read time (by payee, then by amount). It feeds the projection, the annual plan and expected-versus-received, never To Be Assigned. A salary more than 3 days late shows a coach nudge on the dashboard.
- Category kind is derived (payments → scheduled); only "savings" is a user choice.

**Still open:**
 
- Product name and domain.
- Trial starting value in Stripe (suggested: 14 days).
- Onboarding interview scope: how many questions before it feels long? (target: < 2 minutes)
---
 
*This document is the source of truth for v1 scope. Anything not listed in §4.1 is out of scope until this document is revised.*
