from __future__ import annotations

import re
import unicodedata

from .models import InvestigationSeed


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@\-]{1,128}$")


def clean_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def normalize_name(value: str | None) -> str:
    return clean_text(value)


def normalize_username(value: str | None) -> str:
    value = clean_text(value)
    while value.startswith("@"):
        value = value[1:]
    return value.strip()


def normalize_email(value: str | None) -> str:
    return clean_text(value).lower()


def normalize_phone(value: str | None) -> str:
    raw = clean_text(value)
    if not raw:
        return ""
    keep_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    return ("+" if keep_plus else "") + digits


def validate_seed(seed: InvestigationSeed) -> list[str]:
    errors: list[str] = []
    if seed.email and not _EMAIL_RE.match(seed.email):
        errors.append("El correo no tiene un formato válido.")
    if seed.username and not _USERNAME_RE.match(seed.username):
        errors.append("El usuario contiene caracteres no admitidos para esta versión.")
    digits = re.sub(r"\D", "", seed.phone)
    if seed.phone and not (7 <= len(digits) <= 15):
        errors.append("El teléfono debe contener entre 7 y 15 dígitos.")
    if not seed.non_empty_identifiers():
        errors.append("Capture al menos nombre, usuario, correo o teléfono.")
    return errors


def normalize_seed(seed: InvestigationSeed) -> InvestigationSeed:
    return InvestigationSeed(
        person_name=normalize_name(seed.person_name),
        username=normalize_username(seed.username),
        email=normalize_email(seed.email),
        phone=normalize_phone(seed.phone),
        case_id=clean_text(seed.case_id),
        derive_aliases=bool(seed.derive_aliases),
    )


def conservative_alias_candidates(seed: InvestigationSeed) -> list[str]:
    """Return hypotheses only; callers must not treat them as established identity."""
    candidates: list[str] = []
    if seed.email and "@" in seed.email:
        local = seed.email.split("@", 1)[0]
        if 3 <= len(local) <= 64 and _USERNAME_RE.match(local):
            candidates.append(local)
    return list(dict.fromkeys(candidates))


def ascii_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()
