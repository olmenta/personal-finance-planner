## REMOVED Requirements

### Requirement: Late debt payment nudge

**Reason**: A late debt payment becomes one kind of coach proposal (`late_debt_payment`), shown in the coach feed and, when it's the most urgent, in the single dashboard coach capsule.

**Migration**: See coach-proposals: same detection (a required debt payment more than 3 days late in the month overview), same link to "What you owe". Dismissal moves from per-browser storage to server-side state ("Not now" hides it for a week).
