## REMOVED Requirements

### Requirement: Late income nudge on the dashboard

**Reason**: Late income becomes one kind of coach proposal (`late_income`), shown in the coach feed and, when it's the most urgent, in the single dashboard coach capsule.

**Migration**: See coach-proposals: same detection (an occurrence more than 3 days late), same actions ("Add it" with the amount and payer prefilled, "It's already here" opening the income breakdown). Dismissal moves from per-browser storage to server-side state ("Not now" hides it for a week).
