# Olmenta: Personal Finance Planner

Subscription web app that teaches people who have never budgeted to use simplified zero-based budgeting (YNAB-style), with AI removing the onboarding friction. Spanish launch, euros, GDPR. Full product scope and architecture: [project-definition.md](project-definition.md).

## Monorepo layout

| Directory | Contents |
|-----------|----------|
| `webapp/` | Next.js web app (the only shipping frontend for v1) |
| `backend/` | Python FastAPI API |
| `mobile/` | Ionic mobile app — **future release**, does not exist yet |

## Toolchain rules (mandatory)

- **Backend:** Python version is pinned with **uv** (`backend/.python-version`). Use **uv** for everything — install libraries with `uv add <pkg>`, run scripts with `uv run <script>`, serve with **uvicorn** via `uv run uvicorn app.main:app --reload`. Never call `pip` or system Python directly.
- **Frontend:** Node version is pinned with **Volta** (`volta` field in `webapp/package.json`). Always use Volta to install libraries and run npm: `volta run npm install`, `volta run npm run dev` (or Volta shims, which resolve `node`/`npm` to the pinned version). Never bypass the pin with a system Node.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15+ (App Router, TypeScript, `webapp/src/` layout, `@/*` → `src/*`) |
| Styling | Olmenta design system (CSS custom properties in `webapp/src/styles/tokens/`) + Tailwind CSS v4 + shadcn/ui |
| UI components | Olmenta primitives in `webapp/src/components/ui/` (PascalCase); shadcn/ui components in `webapp/src/components/shadcn/` (lowercase) |
| Icons | lucide-react only, via the `Icon` name-map wrapper (`webapp/src/components/ui/Icon.tsx`) — no emoji as icons, no hand-rolled SVGs (exception: the Olmenta logo mark) |
| Fonts | Inter (UI + display + money) and Geist Mono (metadata, account numbers) via `next/font/google`, exposed as `--font-inter` / `--font-geist-mono` |
| Server state (planned) | TanStack Query with optimistic updates |
| i18n (planned) | next-intl, `es` as only active locale — no hard-coded user-facing strings once wired |
| Auth (planned) | Auth0 (Universal Login; RS256 JWT validated by backend) |
| Billing (planned) | Stripe (configurable trial + 5 €/month) |
| Backend | Python 3.12 + FastAPI in `backend/`, served with uvicorn, behind Next.js Route Handlers (BFF) — the browser never calls the Python API directly |
| Mobile (future) | Ionic in `mobile/` — future release |

## Commands

Webapp (run inside `webapp/`):

- `volta run npm run dev` — dev server
- `volta run npm run build` — production build (run before committing significant changes)
- `volta run npm run lint` — lint

Backend (run inside `backend/`):

- `uv sync` — install dependencies
- `uv run uvicorn app.main:app --reload` — dev server
- `uv run pytest` — tests

## Design system (Olmenta)

The UI implements the **Olmenta** design system: violet `#7C5CFC` primary (intelligence, the action color) + mint `#16C79A` accent (the coach, growth), Inter type, white 24px-radius cards on a faintly violet-tinted background (`#F5F3FB`). Calm, premium fintech with a warm human voice. *Spend the violet in one place — if everything is violet, nothing is.*

- **Always style with semantic tokens** (`var(--brand)`, `--accent`, `--text-strong)`, `--surface`, `--income`, `--expense`, `--border-hairline`), never raw hex or raw scale steps. Tokens live in `webapp/src/styles/tokens/*.css`; typography helper classes (`.ol-eyebrow`, `.ol-money`, `.ol-mono`, …) in `typography.css`.
- **Compose the primitives** in `webapp/src/components/ui/` (Icon, Button, IconButton, Badge, SegmentedControl, Avatar, Switch, Input, SearchInput, IconChip, BalanceCard, StatCard, TransactionRow, BudgetBar, Panel, CoachCapsule, CoachMessage, CoachSuggestion) instead of re-implementing them per screen.
- **Semantic color is reserved for money direction**: income green `--income`, expense red `--expense` — never decorative. Charts use the `--chart-*` palette.
- **The sparkle icon is reserved for the AI coach** (capsule, avatar, "Ask the coach"). The dark `--grad-coach` capsule is the only dark surface. `--shadow-fab` (violet glow) is for the FAB only.
- **shadcn/ui** is themed through the `@theme inline` block in `webapp/src/app/globals.css`, which maps Tailwind's color namespace onto Olmenta tokens. Add components with `volta run npx shadcn@latest add <name>` — they land in `webapp/src/components/shadcn/` (alias set in `components.json`; do not change it to `src/components/ui`, the PascalCase files would collide on macOS's case-insensitive filesystem).
- **Money**: tabular numerals always (`fontVariantNumeric: tabular-nums` or `.ol-tnum`), weight 700–800 with tight negative tracking for big figures, euro format via `money()` / `euro()` in `webapp/src/lib/format.ts` (es-ES locale: `4.212,34 €`).
- **Voice**: second person ("you're spending 18% more on dining"); the coach says "I" sparingly. Sentence case everywhere; UPPERCASE only for tiny eyebrow labels. Action labels are verbs that say exactly what happens ("Add transaction", "Set the cap" — never "Submit"). At most one emoji, only inside coach conversation copy. Empty states invite action, never apologize.
- **Motion**: 120–280 ms, `--ease-out` default, `--ease-spring` for presses (buttons scale 0.97, icon buttons 0.94); hover darkens one step (500 → 600) or fills ghosts with `--violet-50`. Honor `prefers-reduced-motion`. No looping/decorative animation.

## Conventions

- App routes live under `webapp/src/app/(app)/` and share the shell ([layout.tsx](webapp/src/app/(app)/layout.tsx)): desktop sidebar ≥1024px + persistent Coach rail ≥1440px; mobile bottom nav with a centered violet FAB below 1024px.
- Responsive behavior comes from the utility classes in `globals.css` (`.grid-dash-top`, `.grid-dash-mid`, `.grid-goals`, `.grid-2`) — reuse them rather than new one-off media queries.
- Mock data lives in `webapp/src/lib/mock-data.ts` until the backend is wired up; keep screens reading from there so the swap to real APIs is mechanical.
- Code and documentation in English; user-facing copy is English placeholder until next-intl lands (then `es`).
- The design-system source of truth (handoff bundle: tokens, component specs, UI-kit prototypes) is the Claude Design export in `design-system/Olmenta Design System-handoff.zip`; `ui-experiments/` holds earlier static HTML explorations.

## Best practices

- TypeScript strict; type component props with exported interfaces.
- Server components by default; add `"use client"` only where state/handlers/hover effects require it.
- Less than 5 seconds to register an expense is the core UX promise — keep entry flows free of unnecessary steps, confirmations, or layout shift.
- Never log or expose financial data in errors/telemetry; no PII in analytics events (GDPR).
- Architecture must stay ready for Open Banking (v3): keep transaction ingestion behind an interface, CSV import is just the first provider.
