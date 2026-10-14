## 1. Home API

- [x] 1.1 `schemas.py`: `HomeSummary`, `HomeReason`, `HomeData`, `HomeFuture`, `HomeGroup`, `HomeView` (with `priority`, `groups`, `snapshot_version`).
- [x] 1.2 `services/home.py::build_home`:
  - the summary mapping (D1);
  - status and reasons (D2), with the overspent categories from the current budget view;
  - the data status (D3: last transaction, uncategorized outflows, pending import, income known, limited with the 14-day constant);
  - the Future status from `projection.upcoming` (D4);
  - priority and groups from `coach.visible` (D5);
  - the snapshot version (D6).
- [x] 1.3 `routers/home.py`: `GET /home`, registered in `main.py`.
- [x] 1.4 Tests:
  - the identity on generated data;
  - the screenshot mapping (L = left − overspent);
  - `needs_organizing` with each reason, `organized`, `no_accounts`;
  - `limited` for a pending import, uncategorized outflows and stale data;
  - Future `unknown`, `on_track`, and `needs_attention` from short payments and from underfunded set-asides alone;
  - the priority not repeated in groups, and group order;
  - the snapshot version stable and changing after a write.

## 2. Navigation

- [x] 2.1 `Sidebar`: Home, Budget, Transactions, Future, Accounts, then Settings. `/debts` highlights Accounts. Remove Goals and Coach.
- [x] 2.2 `BottomNav`: the five labeled destinations around the FAB. `TopBar`: a Settings icon link on mobile.
- [x] 2.3 Move `app/(app)/upcoming` → `app/(app)/future` (title "Future"). `/upcoming` redirects to `/future`, keeping `month`. `/coach` redirects to `/`. Remove `CoachRail` from the layout. Update every internal link (`/upcoming` in proposals' `href`, ThisMonth/Home links, ScheduleEditor and DebtEditor references).
- [x] 2.4 Backend: the coach `short_months` proposal `href` points to `/future?month=`.

## 3. Home screen

- [x] 3.1 BFF route `api/home`. `lib/api.ts` types and `fetchHome`. `invalidateMoneyQueries` adds `home`.
- [x] 3.2 `components/home/`:
  - `HomeHeader` (month, "Updated HH:MM", last transaction, "Review data" linking to what limits it);
  - `CoachLine` (deterministic copy per status and reason);
  - `MonthWidget` (Paid, Still to pay covered/short, Left to spend or "Needs organizing" with reasons, Saved, Unassigned; "View exact breakdown" listing M = T + L + F + U);
  - `PriorityAction` (reusing `ProposalCard`);
  - `RecommendationGroups` (three collapsed groups with counts, expanding to cards; "See more");
  - `FutureWidget` (qualified status, link to Future);
  - `NoAccounts`.
- [x] 3.3 Rewrite `app/(app)/page.tsx` as Home. Remove the "Este mes" panel, `CoachTopCapsule`, the weekly chart and recent transactions from it. Keep the add-transaction entry (the FAB on mobile, a button in the header on desktop).
- [x] 3.4 Transactions: add the weekly spend chart (moved) below the list.
- [x] 3.5 Accounts: add a "What you owe" card (total, debt-free month or plain explanation, link to `/debts`).
- [x] 3.6 Remove the dead code: `ThisMonth` panel parts no longer used, `CoachTopCapsule` if unused, and the `/coach` page content.

## 4. Docs

- [x] 4.1 Update the end-user guides. In `docs/user-guide.md`:
  - navigation (five destinations);
  - "This month: the home screen" rewritten for Home (status, "Needs organizing", breakdown, priority action, groups, Future widget, Review data);
  - "Your coach" now on Home;
  - "Upcoming payments" → "Future".

  In `docs/debt-guide.md`, "Where to find it" now goes through Accounts.
- [x] 4.2 Check that the deltas match the implementation: `home` and `navigation` added; `month-overview` and `webapp-server-state` requirements removed; `coach-proposals`, `payment-projection`, `debts` and `bff-proxy` modified.

## 5. Verification

- [x] 5.1 `uv run pytest` green in `backend/`.
- [x] 5.2 Type check, lint and build green in `webapp/` (build with `NEXT_DIST_DIR=.next-verify` and the dev-server types excluded).
- [x] 5.3 e2e:
  - update `category-targets.spec.ts` (dashboard assertions → Home and breakdown; `/upcoming` → `/future`), `coach.spec.ts` (feed on Home, no `/coach`), `income.spec.ts` (late income as the priority action) and `debts.spec.ts` (reached from Accounts; the late installment as the priority action);
  - add `e2e/home.spec.ts`: five destinations; "Needs organizing" with reasons and a reconciling breakdown; the priority action not repeated; Future unknown without income; `/upcoming` and `/coach` redirects; mobile navigation;
  - `volta run npm run e2e` green.
