## REMOVED Requirements

### Requirement: Home screen "Este mes" card

**Reason**: The redesign replaces the long "Este mes" panel with Home's month widget, status and exact breakdown (capability `home`).

**Migration**: Home reads the same `GET /overview/{month}` contract through `GET /home`. Already paid (with partial payments and card payments), still to pay with coverage, saved and unassigned keep their meaning. The per-category lists move behind "View exact breakdown" and the Budget screen.
