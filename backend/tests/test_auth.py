"""Auth0 tokens, user provisioning and isolation (openspec change
auth0-users, spec authentication). Tokens are real RS256 JWTs signed with a
key generated here; the tenant's key set is faked."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import func, select

from app import auth
from app.config import ConfigurationError, Settings, check_auth_config, get_settings
from app.models import Account, User
from app.services import users

DOMAIN = "olmenta-test.eu.auth0.com"
AUDIENCE = "https://api-dev.olmenta.com"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def auth0_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "auth0")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("AUTH0_DOMAIN", DOMAIN)
    monkeypatch.setenv("AUTH0_AUDIENCE", AUDIENCE)
    get_settings.cache_clear()
    fake = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=KEY.public_key()))
    monkeypatch.setattr(auth, "_jwks", lambda domain: fake)
    yield
    get_settings.cache_clear()


def token(sub="auth0|ana", email="ana@example.com", aud=AUDIENCE, iss=f"https://{DOMAIN}/", exp_in=3600,
          key=KEY) -> str:
    claims = {"sub": sub, "aud": aud, "iss": iss, "iat": int(time.time()), "exp": int(time.time()) + exp_in}
    if email:
        claims[auth.EMAIL_CLAIM] = email
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


def bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.parametrize(("label", "kwargs"), [
    ("wrong audience", {"aud": "https://api-beta.olmenta.com"}),
    ("wrong issuer", {"iss": "https://someone-else.auth0.com/"}),
    ("expired", {"exp_in": -60}),
    ("bad signature", {"key": OTHER_KEY}),
])
def test_tokens_this_environment_rejects(client, label, kwargs):
    response = client.get("/me", headers=bearer(token(**kwargs)))
    assert response.status_code == 401, label
    assert response.json()["detail"]["code"] == "unauthenticated"
    assert response.headers["www-authenticate"] == "Bearer"


def test_missing_or_malformed_header(client):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_first_visit_creates_the_user_with_a_cash_account(client, db):
    response = client.get("/me", headers=bearer(token()))
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "ana@example.com" and response.json()["locale"] == "es"
    user = db.scalar(select(User).where(User.auth0_sub == "auth0|ana"))
    [account] = db.scalars(select(Account).where(Account.user_id == user.id)).all()
    assert (account.name, account.type) == ("Efectivo", "cash")
    # The second request reuses it.
    client.get("/me", headers=bearer(token()))
    assert db.scalar(select(func.count()).select_from(User).where(User.auth0_sub == "auth0|ana")) == 1


def test_an_existing_user_is_linked_by_email(client, db):
    db.add(User(email="luis@example.com", locale="es"))
    db.flush()
    client.get("/me", headers=bearer(token(sub="auth0|luis", email="Luis@Example.com")))
    linked = db.scalar(select(User).where(User.email == "luis@example.com"))
    assert linked.auth0_sub == "auth0|luis"


def test_parallel_first_requests_create_one_user(db, monkeypatch):
    first = users.resolve(db, "auth0|eva", "eva@example.com")
    calls = {"n": 0}
    real = users._by_sub

    def stale_then_real(session, sub):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(session, sub)

    monkeypatch.setattr(users, "_by_sub", stale_then_real)
    again = users.resolve(db, "auth0|eva", None)
    assert again.id == first.id
    assert db.scalar(select(func.count()).select_from(User).where(User.auth0_sub == "auth0|eva")) == 1


def test_two_people_see_only_their_own_data(client):
    ana, luis = bearer(token()), bearer(token(sub="auth0|luis", email="luis@example.com"))
    client.get("/me", headers=ana)
    client.get("/me", headers=luis)
    response = client.post("/transactions", headers=ana, json={"amount_cents": 1000, "kind": "income",
                                                               "date": "2026-10-02"})
    assert response.status_code == 201, response.text
    assert len(client.get("/transactions", headers=ana).json()) == 1
    assert client.get("/transactions", headers=luis).json() == []
    assert client.get("/coach/conversation", headers=luis).json()["messages"] == []
    luis_budget = client.get("/budget/2026-10", headers=luis).json()
    assert luis_budget["groups"] == []  # Luis hasn't been through onboarding


def test_dev_user_is_refused_outside_local_and_test():
    with pytest.raises(ConfigurationError, match="APP_ENV=beta"):
        check_auth_config(Settings(database_url="postgresql://x", app_env="beta", auth_mode="dev_user"))
    with pytest.raises(ConfigurationError, match="AUTH0_DOMAIN"):
        check_auth_config(Settings(database_url="postgresql://x", app_env="beta", auth_mode="auth0",
                                   auth0_domain=None, auth0_audience=None))
    check_auth_config(Settings(database_url="postgresql://x", app_env="local", auth_mode="dev_user"))
