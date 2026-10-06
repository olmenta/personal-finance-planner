"""Thin client over the local Olmenta REST API (design D1, D6).

The API stays the single source of truth: this module only maps calls and
turns machine error codes into one-line messages the model can act on.
"""

import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx

from .money import eur

DEFAULT_API_URL = "http://127.0.0.1:8000"
START_API = (
    "The Olmenta API isn't running — start it in backend/ with "
    "`uv run uvicorn app.main:app --reload`, then try again."
)


class ToolError(Exception):
    """An error the model should read and act on (not a crash)."""


def is_loopback(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _message(status: int, detail: Any) -> str:
    code = detail.get("code") if isinstance(detail, dict) else None
    available = detail.get("available_cents") if isinstance(detail, dict) else None
    messages = {
        "category_required": "An expense needs a category — pick one with list_categories or ask the user.",
        "category_not_found": "That category doesn't exist (or is archived) — check list_categories.",
        "account_not_found": "That account doesn't exist — check list_accounts.",
        "account_exists": "An active account with that name already exists.",
        "category_exists": "A category with that name already exists in that group.",
        "group_not_found": "That category group doesn't exist — check list_categories.",
        "same_category": "Source and destination are the same category.",
        "same_account": "A transfer needs two different accounts.",
        "payment_category_locked": "Credit-card payment categories and their group are managed by the account, not edited directly.",
        "assignment_from_payments": "This category is assigned from its scheduled payments; change the payments in the app or move money instead.",
        "transaction_not_found": "That transaction doesn't exist or isn't confirmed.",
        "is_transfer": "That row is half of a transfer; edit it as a transfer in the app.",
    }
    if code == "insufficient_available" and available is not None:
        return f"The source category only has {eur(available)} available."
    if code == "insufficient_to_be_assigned" and available is not None:
        return f"To Be Assigned only holds {eur(available)}."
    if code in messages:
        return messages[code]
    return f"The API refused the request ({status}{f', {code}' if code else ''})."


class OlmentaClient:
    """Calls to the REST API used by the tools. `http` is any httpx.Client
    (the real one for the server, a TestClient in tests)."""

    def __init__(self, http: httpx.Client):
        self.http = http

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self.http.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout) as error:
            raise ToolError(START_API) from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise ToolError(_message(response.status_code, detail))
        return None if response.status_code == 204 else response.json()

    # ---- reads -------------------------------------------------------------
    def budget(self, month: str) -> dict:
        return self._request("GET", f"/budget/{month}")

    def overview(self, month: str) -> dict:
        return self._request("GET", f"/overview/{month}")

    def transactions(self, month: str | None) -> list[dict]:
        return self._request("GET", "/transactions", params={"month": month} if month else None)

    def categories(self) -> list[dict]:
        return self._request("GET", "/categories")

    def accounts(self) -> list[dict]:
        return self._request("GET", "/accounts")

    def review(self) -> dict:
        return self._request("POST", "/transactions/review")

    # ---- writes ------------------------------------------------------------
    def add_transaction(self, body: dict) -> dict:
        return self._request("POST", "/transactions", json=body)

    def assign(self, month: str, category_id: str, cents: int) -> dict:
        return self._request(
            "PUT", f"/budget/{month}/assignments/{category_id}", json={"amount_cents": cents}
        )

    def move(self, month: str, body: dict) -> dict:
        return self._request("POST", f"/budget/{month}/moves", json=body)

    def create_category(self, body: dict) -> dict:
        return self._request("POST", "/categories", json=body)

    def create_transfer(self, body: dict) -> dict:
        return self._request("POST", "/transfers", json=body)

    def apply_review(self, decisions: dict) -> dict:
        return self._request("POST", "/transactions/review/apply", json=decisions)
