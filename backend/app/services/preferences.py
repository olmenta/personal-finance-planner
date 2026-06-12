"""Per-user preferences memory access (project-definition §6.6).

All reads/writes of the UserPreferences JSONB document go through
PreferencesStore so the storage backend can change without touching
consumers (category generation, import suggestions, future coach).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import UserPreferences


class PreferencesStore:
    def __init__(self, db: Session):
        self._db = db

    def get(self, user_id: str) -> UserPreferences | None:
        return self._db.scalar(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )

    def put(self, user_id: str, document: dict, prompt_version: str) -> UserPreferences:
        """Create or replace the user's single preferences document."""
        record = self.get(user_id)
        if record is None:
            record = UserPreferences(
                user_id=user_id, preferences=document, prompt_version=prompt_version
            )
            self._db.add(record)
        else:
            record.preferences = document
            record.prompt_version = prompt_version
        self._db.flush()
        return record
