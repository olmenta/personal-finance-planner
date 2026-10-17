## REMOVED Requirements

### Requirement: Dashboard served by the API

**Reason**: The dashboard becomes Home (capability `home`). It no longer shows the weekly chart or the recent transactions.

**Migration**: Home reads `GET /api/home` with TanStack Query (key `["home"]`), invalidated with the other money queries. The weekly spend chart moves to the Transactions screen, still reading `GET /api/summary/{month}`. Recent transactions live in Transactions.
