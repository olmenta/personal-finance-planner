"""Auth0 access tokens (spec: authentication, auth0-users design D3).

The API trusts only RS256 tokens signed by the tenant, issued by
https://<AUTH0_DOMAIN>/ for this environment's API identifier (audience).
Tokens and emails are never logged.
"""

from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient, PyJWKClientError

from .config import get_settings

EMAIL_CLAIM = "https://olmenta.com/email"  # added by the post-login Action


class Unauthenticated(Exception):
    """No token, or a token this environment doesn't accept → 401."""


class AuthUnavailable(Exception):
    """The tenant's keys can't be fetched → 503 (visible, not a 401)."""


@dataclass(frozen=True)
class Identity:
    sub: str
    email: str | None


@lru_cache
def _jwks(domain: str) -> PyJWKClient:
    return PyJWKClient(f"https://{domain}/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def _signing_key(token: str, domain: str):
    try:
        return _jwks(domain).get_signing_key_from_jwt(token).key
    except PyJWKClientError as error:
        # An unknown key id (rotation) refetches once; a fetch failure is 503.
        if "Unable to find a signing key" in str(error):
            _jwks.cache_clear()
            try:
                return _jwks(domain).get_signing_key_from_jwt(token).key
            except PyJWKClientError as again:
                raise Unauthenticated() from again
        raise AuthUnavailable() from error
    except jwt.DecodeError as error:
        raise Unauthenticated() from error


def verify(token: str) -> Identity:
    settings = get_settings()
    domain, audience = settings.auth0_domain, settings.auth0_audience
    key = _signing_key(token, domain)
    try:
        claims = jwt.decode(
            token, key, algorithms=["RS256"], audience=audience, issuer=f"https://{domain}/",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as error:
        raise Unauthenticated() from error
    email = claims.get(EMAIL_CLAIM)
    return Identity(sub=claims["sub"], email=email.strip().lower() if isinstance(email, str) else None)
