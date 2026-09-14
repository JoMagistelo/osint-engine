from __future__ import annotations

import re
from dataclasses import dataclass

from .models import InvestigationSeed


_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


@dataclass(frozen=True, slots=True)
class UsernameCandidate:
    value: str
    origin: str
    confidence: float
    relation: str
    parent_value: str


def clean_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def normalize_name(value: str | None) -> str:
    return clean_text(value)


def normalize_username(value: str | None) -> str:
    """Normaliza el objetivo que se enviará a Maigret.

    Acepta un alias puro, ``@alias`` o texto con forma de correo. En este
    último caso sólo conserva la parte anterior a ``@`` porque Maigret busca
    nombres de usuario, no direcciones de correo completas.
    """

    normalized = clean_text(value)
    if normalized.lower().startswith("mailto:"):
        normalized = normalized[7:].strip()
    while normalized.startswith("@"):
        normalized = normalized[1:]

    if "@" in normalized:
        local_part, domain = normalized.split("@", 1)
        if local_part and domain:
            normalized = local_part

    return normalized.strip()


def normalize_phone(value: str | None) -> str:
    raw = clean_text(value)
    if not raw:
        return ""
    keep_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    return ("+" if keep_plus else "") + digits


def validate_seed(seed: InvestigationSeed) -> list[str]:
    errors: list[str] = []
    if seed.username and not _USERNAME_RE.fullmatch(seed.username):
        errors.append("El usuario contiene caracteres no admitidos por Maigret.")
    digits = re.sub(r"\D", "", seed.phone)
    if seed.phone and not (7 <= len(digits) <= 15):
        errors.append("El teléfono debe contener entre 7 y 15 dígitos.")
    if not seed.non_empty_identifiers():
        errors.append("Capture un usuario, nombre o teléfono.")
    return errors


def normalize_seed(seed: InvestigationSeed) -> InvestigationSeed:
    return InvestigationSeed(
        person_name=normalize_name(seed.person_name),
        username=normalize_username(seed.username),
        phone=normalize_phone(seed.phone),
        case_id=clean_text(seed.case_id),
        email="",
        derive_aliases=False,
    )


def username_search_candidates(seed: InvestigationSeed) -> list[UsernameCandidate]:
    """Construye el plan de Maigret exclusivamente desde el usuario explícito.

    Nombre y teléfono son objetivos independientes. No se generan alias desde
    ellos y tampoco se infiere identidad a partir de una dirección de correo.
    Si el operador pega ``alias@dominio`` en el campo Usuario, ``normalize_seed``
    lo transforma previamente en ``alias``.
    """

    username = normalize_username(seed.username)
    if not username or not _USERNAME_RE.fullmatch(username):
        return []
    return [
        UsernameCandidate(
            value=username,
            origin="provided_username",
            confidence=1.0,
            relation="provided_username",
            parent_value=username,
        )
    ]


def conservative_alias_candidates(seed: InvestigationSeed) -> list[str]:
    """Compatibilidad con la API previa: ya no deriva alias automáticamente."""

    return []
