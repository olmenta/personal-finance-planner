"""Names in, ids inside, for the coach's tools (coach-conversation D4): the
model refers to categories, accounts and payees by name. An unknown or
ambiguous name is an error listing candidates, so the model asks instead of
guessing. Same conventions as the dev MCP server."""

import unicodedata
from collections.abc import Iterable

MAX_CANDIDATES = 8


class UnknownName(LookupError):
    pass


def fold(text: str) -> str:
    """Case- and accent-insensitive: "Transporte público" ~ "transporte publico"."""
    decomposed = unicodedata.normalize("NFKD", text.strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def resolve(name: str, options: Iterable[tuple[str, str]], kind: str) -> str:
    """(name, id) options -> the id of the exact match, else the single
    partial match; otherwise raise with candidates."""
    options = list(options)
    wanted = fold(name)
    exact = [oid for oname, oid in options if fold(oname) == wanted]
    if len(exact) == 1:
        return exact[0]
    partial = [(oname, oid) for oname, oid in options if wanted and wanted in fold(oname)]
    if not exact and len(partial) == 1:
        return partial[0][1]
    if exact or partial:
        names = sorted({oname for oname, _ in (partial or options)})[:MAX_CANDIDATES]
        raise UnknownName(f"{kind} {name!r} is ambiguous; candidates: {', '.join(names)}. Ask which one.")
    known = sorted(oname for oname, _ in options)[:MAX_CANDIDATES]
    hint = f" Known {kind}s include: {', '.join(known)}." if known else ""
    raise UnknownName(f"No {kind} named {name!r}.{hint} Don't invent one; ask or list them.")


# Words that name an account by its type when no account has that name
# (coach-budget-setup design D4): "pagué en efectivo" → the cash account.
ACCOUNT_TYPE_WORDS = {
    "efectivo": "cash", "cash": "cash", "metalico": "cash",
    "tarjeta": "credit", "card": "credit", "credito": "credit",
    "banco": "bank", "cuenta": "bank", "bank": "bank",
}


def resolve_account(name: str, accounts: Iterable[tuple[str, str, str]]) -> str:
    """(name, id, type) options -> the account named `name`; else, when the
    text names a type ("efectivo", "tarjeta"…), the only active account of
    that type. Several of that type is an error listing them."""
    accounts = list(accounts)
    try:
        return resolve(name, [(n, i) for n, i, _ in accounts], "account")
    except UnknownName as error:
        kinds = {ACCOUNT_TYPE_WORDS[w] for w in fold(name).split() if w in ACCOUNT_TYPE_WORDS}
        if len(kinds) != 1:
            raise error
        kind = kinds.pop()
        of_type = [(n, i) for n, i, t in accounts if t == kind]
        if len(of_type) == 1:
            return of_type[0][1]
        if of_type:
            listed = ", ".join(sorted(n for n, _ in of_type))
            raise UnknownName(f"There are several {kind} accounts: {listed}. Ask which one.") from error
        raise error
