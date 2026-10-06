"""Names in, ids inside: the model refers to categories, groups and accounts
by name; an unknown or ambiguous name is an error that lists candidates so
the model asks instead of guessing (design D3)."""

import unicodedata
from collections.abc import Iterable

MAX_CANDIDATES = 8


class NameError_(LookupError):  # noqa: N801 — avoid shadowing the builtin
    pass


def _fold(text: str) -> str:
    """Case- and accent-insensitive: "Transporte público" ~ "transporte publico"."""
    decomposed = unicodedata.normalize("NFKD", text.strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def resolve(name: str, options: Iterable[tuple[str, str]], kind: str) -> str:
    """(name, id) options -> the id of the exact match, else the single
    partial match; otherwise raise with candidates."""
    options = list(options)
    wanted = _fold(name)
    exact = [oid for oname, oid in options if _fold(oname) == wanted]
    if len(exact) == 1:
        return exact[0]
    partial = [(oname, oid) for oname, oid in options if wanted and wanted in _fold(oname)]
    if not exact and len(partial) == 1:
        return partial[0][1]
    if exact or partial:
        names = sorted({oname for oname, _ in (partial or options)})[:MAX_CANDIDATES]
        raise NameError_(
            f"{kind} {name!r} is ambiguous — candidates: {', '.join(names)}. Ask which one."
        )
    known = sorted(oname for oname, _ in options)[:MAX_CANDIDATES]
    hint = f" Known {kind}s include: {', '.join(known)}." if known else ""
    raise NameError_(f"No {kind} named {name!r}.{hint} Don't invent one — ask or list them.")
