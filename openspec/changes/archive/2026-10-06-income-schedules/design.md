## Context

Expected income today is one integer, `income.expected_monthly_cents` in the `UserPreferences` JSONB document. The onboarding interview writes it, and `PUT /plan/income` edits it. Three consumers read it:

- `services/projection.py`, which flattens it into every simulated month and multiplies it by 12 for the annual summary;
- `IncomeBreakdown.tsx`, which shows "expected X · received Y" through `GET /api/plan/income`;
- the Upcoming payments inline prompt.

Real income is unchanged by this change: confirmed uncategorized inflows feed `income_cents` and To Be Assigned (principle 1).

Payment schedules (`payment_schedules`, `services/schedules.py`) already solve "when does money move": per-pattern pydantic models, a pure `occurs(schedule, month)`, and read-time matching of spending to occurrences in the month overview. Income is the same problem in the opposite direction, so this design reuses that machinery instead of inventing a second rule language.

## Goals / Non-Goals

**Goals:**

- Model expected income per source, with a rule and day, and support 14 pagas, several incomes, and finite or one-off income.
- Show expected versus received per occurrence (received with difference, pending, late, missed) and surface unplanned income.
- Make the projection and the annual plan month-accurate, including carrying this month's still-due salary into next month.
- Keep principle 1 intact: schedules never create transactions or touch budget math.

**Non-Goals:**

- Assigning planned income before it arrives. That would break principle 1 and the accounts identity.
- Probable income (bonuses that depend on targets). There is still no field for it.
- Auto-creating income transactions from schedules, or push or email notifications when income is late. Only the in-app dashboard nudge (D9) is in scope.
- Suggesting schedule amount updates when received amounts drift. This is a later coach insight.
- Per-account expected income, and gross-to-net salary calculation.

## Decisions

### D1. Separate `income_schedules` table, shared rule columns

A new table `income_schedules(id, user_id, name, amount_cents, payee_id, pattern, months, month, every_n, start_month, count, once_month, day, estimated, created_at)` has the same rule columns as `payment_schedules`, without `category_id` and with `payee_id`. A SQLAlchemy mixin (`ScheduleRuleMixin`) declares the shared rule columns once.

*Alternative considered:* making `payment_schedules.category_id` nullable and adding a `direction` column. Rejected because every existing query (`schedules_by_category`, catch-up, computed assignments, the editor) would need a direction filter. A forgotten filter would silently put income into a category's catch-up math, and income has no category, no catch-up and no `no_date`.

### D2. One rule engine

`occurs()`, `month_index` and the pattern pydantic models stay in `services/schedules.py` and `schemas.py`. `occurs()` is typed against a small `ScheduleRule` Protocol (the rule fields), so both ORM models pass. The income input union reuses `MonthlySchedule | SomeMonthsSchedule | AnnualSchedule | EveryNSchedule | OnceSchedule`, each extended with `payer: str | None` (a name resolved to `payee_id`, see D3). `NoDateSchedule` is left out, so `no_date` fails discriminator validation with 422 `invalid_schedule` and no extra code.

### D3. Payer as a payee reference, resolved by name on write

`income_schedules.payee_id` is a nullable foreign key to `payees`, with `ON DELETE SET NULL`. The API accepts a `payer` name and runs it through the same resolution transactions use (`services/payees.py`: case-insensitive match on the trimmed name, or create), so a schedule can name a payer the user hasn't been paid by yet. This is the normal case at onboarding. Matching compares `payee_id`, the same column transactions already carry.

This extends the payees rule "born from transaction writes" to income schedule writes. There is still no public payee endpoint. Discarding an import batch must also keep payees that an income schedule references (payees delta).

*Alternative considered:* free-text `payer` compared by name. It needed no payees change, but renaming or merging a payee would silently break matching, typos would create ghost payers that match nothing, and comparing names duplicates logic that payee resolution already owns.

### D4. Read-time matching, no persisted links

`services/income.py::month_income(db, user, month)` computes occurrences and their status on every read, the same way the month overview matches payments. It works in two passes:

1. **Payer pass.** Whole inflows go to the earliest unreceived occurrence of that payer. An inflow that reaches at least 90 % of the next occurrence's running sum also covers it, which handles a June salary and extra pay arriving together.
2. **Amount pass.** Schedules without a payee are matched within ±10 % (±25 % when estimated).

Inflows are assigned whole, never split across a received occurrence and the unplanned list, so a bonus from the employer shows up as unplanned income instead of hiding as a salary "difference".

"Linking" an unplanned inflow writes payee equality (the transaction's payee or the schedule's `payee_id`) through existing endpoints, so a correction persists without a link table and teaches future months.

*Alternative considered:* an `income_schedule_id` column on transactions, set at confirm time. Rejected because it needs backfill, has to stay consistent when transactions or schedules are edited and deleted, and adds a step to imports. Derived matching recomputes correctly after any edit.

Lateness uses `clock` (Europe/Madrid) with a 3-day grace after the occurrence's day. A missing day counts as the last day of the month, so it is never late before the month closes. `opening_balance` rows are excluded from matching but still count as received income, because budget math is unchanged.

### D5. Projection: month money from occurrences, carry still-due income

In `projection.upcoming`:

- `money = income + tba` becomes `money = expected_in(m) + tba`.
- The projected end of month M adds `still_expected_cents` from `month_income(M)`: pending and late occurrences only, never missed ones.

`summary.income_cents` becomes the sum of occurrences over the window. Month M counts all of its occurrences, received or not, because the annual plan compares plans and not cash.

`income_known` becomes "has at least one income schedule". `expected_income` and `set_expected_income` are deleted, and `UpcomingMonth` gains `expected_income_cents`.

### D6. Migration converts the preference, then planning stops reading it

The Alembic revision runs as follows:

1. It creates `income_schedules`.
2. It runs a data step in SQL over `user_preferences`: when `preferences->'income'->>'expected_monthly_cents'` is a positive integer, it inserts one `monthly` schedule named "Monthly income", with `day` from `income_day` when it is between 1 and 31.

The preference keys are left in place as interview memory, with no reader. The downgrade drops the table, and the preference was never deleted.

### D7. Onboarding prompt v3

The extraction schema has `income.sources[]: {name, payer, amount_cents, day, payments_per_year: 12|14}`. The proposal builder turns each source into one `monthly` schedule plus, for 14, a `some_months [6,12]` "Paga extra". This deterministic mapping lives in code, not in the LLM. Finalize creates the schedules inside the same transaction. Eval (`uv run python -m evals onboarding`, 2026-10-06): the suite, including the new `income_two_sources_extra_pays_and_bonus` case, passed with no regressions against v2. v1 and v2 stay readable for existing sessions. Their `{expected_monthly_cents, income_day}` maps to one monthly source.

### D8. Webapp: extract the rule form from `ScheduleEditor`

The pattern picker and the rule fields move out of `components/plan/ScheduleEditor.tsx` into `components/plan/ScheduleRuleFields.tsx`. The sentence description stays in `describe()` in `lib/schedules.ts`, widened to accept income schedules. The new `components/plan/IncomeEditor.tsx`, at Settings → Income and as a sheet from Upcoming payments, composes them with a payer combobox (from `GET /api/payees`) and the "14 payments a year" shortcut. The shortcut posts the companion `some_months` schedule.

Server state uses TanStack Query keys `["income-schedules"]` and `["income", month]`. Schedule mutations invalidate those keys plus `plan/upcoming` and `plan/summary`. Linking (a transaction PATCH) invalidates `["income", month]`.

### D9. Late-income nudge as a dashboard coach capsule

The dashboard reads `GET /api/income/{current month}` and shows one `CoachCapsule` when any occurrence is `late`. It doesn't need another endpoint, because lateness is already in the contract.

- **Actions.** Both reuse existing UI: "Add it" opens the add-transaction dialog prefilled as income (amount and payer, so the payer pass matches it immediately), and "It's already here" opens the income breakdown to link an inflow.
- **Dismissal.** It is a per-viewer convenience, stored in `localStorage` under the month and the set of late schedule ids, wrapped in try/catch. A new late occurrence changes the key and brings the capsule back.
- **Placement.** It sits on the dashboard only, not in the Coach rail, because v1 has no free-form coach chat.

*Alternative considered:* a server-side dismissal flag in preferences. Rejected because it's not shared state, and losing it only shows the nudge again.

The 3-day grace was confirmed as is. A transfer on the 27th that lands on the 30th after a weekend is still not late.

## Risks / Trade-offs

- **[Imported inflows have no payee, and amount matching picks the wrong schedule when two incomes have similar amounts]** → Tolerance is tight (10 %), closest amount and day break ties, and one "This is…" link fixes it permanently through payer equality.
- **[A payee created from a schedule shows up in autocomplete before any transaction uses it]** → This is intended, because it is the payer the user just named, and it matches how onboarding seeds payers.
- **[The 90 % rule over-merges: a large single inflow covers two occurrences when it was really salary plus bonus]** → It only chains occurrences of the same payer within the same month. The result reads as "both received", and the user can see the totals in the breakdown. This is acceptable for v1.
- **[Carrying still-due income makes November look funded although the salary might not come]** → Only `pending` and `late` occurrences carry, `missed` never does, and the current month's real coverage is never based on expected money.
- **[BREAKING removal of `/plan/income`]** → The only consumers are inside this repo (the webapp BFF route, `api.ts`, IncomeBreakdown, tests). The MCP server doesn't use it. Everything changes in one PR.

## Migration Plan

1. Deploy the backend with the migration. Existing users get their monthly figure as one schedule, and the projection output is identical except where income is still due this month.
2. Deploy the webapp in the same release. The BFF route `/api/plan/income` is removed together with the backend endpoint.
3. Rollback: downgrade drops `income_schedules`. The preference value is still there, so restoring the previous build restores the old behavior.

## Open Questions

- None open. Resolved 2026-10-06: the coach shows a late-income nudge on the dashboard (D9), and the 3-day lateness grace is kept.
