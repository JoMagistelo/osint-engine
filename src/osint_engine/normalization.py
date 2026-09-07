from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .models import InvestigationSeed


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@\-]{1,128}$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


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


def ascii_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _valid_username_candidate(value: str) -> bool:
    return 3 <= len(value) <= 64 and bool(_USERNAME_RE.fullmatch(value))


def username_search_candidates(seed: InvestigationSeed) -> list[UsernameCandidate]:
    """Build the usernames Maigret will check.

    The explicit username is authoritative as a search seed. The local-part
    of an operator-provided email is checked automatically because this is a
    common OSINT pivot, but remains a hypothesis about account ownership.
    Name-derived variants are always low-confidence hypotheses.
    """

    candidates: list[UsernameCandidate] = []
    seen: set[str] = set()

    def add(
        value: str,
        *,
        origin: str,
        confidence: float,
        relation: str,
        parent_value: str,
    ) -> None:
        value = normalize_username(value)
        key = value.casefold()
        if not value or key in seen or not _valid_username_candidate(value):
            return
        seen.add(key)
        candidates.append(
            UsernameCandidate(
                value=value,
                origin=origin,
                confidence=confidence,
                relation=relation,
                parent_value=parent_value,
            )
        )

    if seed.username:
        add(
            seed.username,
            origin="provided_username",
            confidence=1.0,
            relation="provided_username",
            parent_value=seed.username,
        )

    # El texto anterior a @ se consulta siempre. Es un pivote útil, no prueba
    # que las cuentas encontradas pertenezcan al titular del correo.
    if seed.email and "@" in seed.email:
        local = seed.email.split("@", 1)[0]
        add(
            local,
            origin="email_local_part",
            confidence=0.68,
            relation="derived_from_email",
            parent_value=seed.email,
        )

    if seed.person_name:
        tokens = [t for t in _TOKEN_RE.findall(ascii_key(seed.person_name)) if len(t) >= 2]
        variants: list[str] = []
        if len(tokens) == 1:
            variants = [tokens[0]]
        elif len(tokens) >= 2:
            first, last = tokens[0], tokens[-1]
            middle = tokens[1:-1]

            # Dos formas habituales se prueban automáticamente para que una
            # investigación basada sólo en nombre sea útil desde el inicio.
            variants = [
                first + last,
                f"{first}.{last}",
            ]

            # El modo ampliado agrega permutaciones más ruidosas.
            if seed.derive_aliases:
                variants.extend(
                    [
                        f"{first}_{last}",
                        f"{first}-{last}",
                        first[0] + last,
                        first + last[0],
                        "".join(tokens),
                        ".".join(tokens),
                    ]
                )
                if middle:
                    variants.extend(
                        [
                            first + middle[0][0] + last,
                            first[0] + "".join(part[0] for part in middle) + last,
                        ]
                    )

        for value in variants[:10]:
            add(
                value,
                origin="name_variant",
                confidence=0.25,
                relation="derived_from_name",
                parent_value=seed.person_name,
            )

    return candidates


def conservative_alias_candidates(seed: InvestigationSeed) -> list[str]:
    """Compatibility helper returning non-explicit username hypotheses."""
    return [
        candidate.value
        for candidate in username_search_candidates(seed)
        if candidate.origin != "provided_username"
    ]
