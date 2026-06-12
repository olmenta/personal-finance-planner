# Tasks — Resume pending imports

## 1. Backend API

- [x] 1.1 409 guard in `POST /imports`: existing staged batch for the user → 409 `import_pending` with the pending batch id in the detail (design D1)
- [x] 1.2 `GET /imports/pending` in `backend/app/routers/imports.py`: full `ImportBatchView` of the user's staged batch or 404 `no_pending_import`; declared **before** `GET /imports/{batch_id}` (design D2)
- [x] 1.3 Tests in `backend/tests/test_imports.py`: second upload 409 with batch id, upload allowed after discard and after confirm, pending fetch returns staged rows, 404 when none; `uv run pytest` green

## 2. BFF and client

- [x] 2.1 `webapp/src/app/api/imports/pending/route.ts` (GET via `proxyFetch`)
- [x] 2.2 `webapp/src/lib/api.ts`: `fetchPendingImport(): Promise<ImportBatchView | null>` (404 → null, other errors throw)

## 3. UI

- [x] 3.1 `["imports", "pending"]` query on the transactions screen; persistent banner (panel style, info tone) with filename, row count, "Resume review" action when a pending batch exists (design D3)
- [x] 3.2 `ImportBankTransactionsDialog` resume mode: opening with a pending batch (from the banner or the regular button) lands on the review step with discard available; upload/confirm/discard invalidate `["imports", "pending"]`
- [x] 3.3 409 `import_pending` on upload navigates to the pending review instead of rendering an error (design D5)
- [x] 3.4 Skip copy: "N rows already imported — skipped"; all-skipped upload renders the explanatory empty state pointing to the transactions list (design D4)

## 4. Verification

- [x] 4.1 `uv run pytest` green (TEST_DATABASE_URL exported); `volta run npm run build` + `volta run npm run lint` green
- [x] 4.2 E2E with both processes: upload → close review → banner appears → resume shows staged rows → second upload attempt 409s into the same review → confirm clears the banner; re-upload of the confirmed file shows the already-imported empty state
- [x] 4.3 At sync/archive time: merge the `bff-proxy` endpoint list and the `webapp-server-state` statement-import requirement with whatever has landed since 2026-06-12
