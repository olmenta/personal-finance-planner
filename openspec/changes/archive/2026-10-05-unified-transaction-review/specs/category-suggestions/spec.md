# category-suggestions Delta Specification

## REMOVED Requirements

### Requirement: On-demand categorization proposals

**Reason**: Replaced by the transaction review (capability `transaction-review`), which lists every confirmed uncategorized transaction with the AI suggestion as a default and applies the same decisions as an import confirmation (category, payee, note, transfer, twin match). A separate proposals/apply pair with narrower semantics is no longer needed.
**Migration**: Use `POST /transactions/review` instead of `POST /transactions/suggest-categories`, and `POST /transactions/review/apply` (import-style decision maps) instead of `POST /transactions/apply-categories`. The BFF routes `/api/transactions/suggest-categories` and `/api/transactions/apply-categories` are removed with them; the webapp was their only client.
