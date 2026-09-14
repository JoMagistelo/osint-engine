from osint_engine.models import InvestigationSeed
from osint_engine.normalization import (
    conservative_alias_candidates,
    normalize_seed,
    normalize_username,
    username_search_candidates,
    validate_seed,
)


def test_normalize_seed_limits_scope_to_supported_identifiers():
    seed = normalize_seed(
        InvestigationSeed(
            person_name="  José   Pérez ",
            username="@@Usuario_01",
            phone="+52 (55) 1234-5678",
            email="legacy@example.com",
            derive_aliases=True,
        )
    )
    assert seed.person_name == "José Pérez"
    assert seed.username == "Usuario_01"
    assert seed.phone == "+525512345678"
    assert seed.email == ""
    assert seed.derive_aliases is False
    assert not validate_seed(seed)


def test_email_shaped_username_uses_only_local_part_for_maigret():
    assert normalize_username("jose.gomez@afasasda.com") == "jose.gomez"
    seed = normalize_seed(InvestigationSeed(username="jose.gomez@afasasda.com"))
    plan = username_search_candidates(seed)
    assert [(item.value, item.origin) for item in plan] == [
        ("jose.gomez", "provided_username")
    ]


def test_maigret_plan_does_not_derive_usernames_from_name_or_legacy_email():
    seed = normalize_seed(
        InvestigationSeed(
            person_name="José Cruz Gómez Rodríguez",
            email="jose.gomez@example.com",
            derive_aliases=True,
        )
    )
    assert username_search_candidates(seed) == []
    assert conservative_alias_candidates(seed) == []


def test_phone_is_a_valid_independent_target():
    seed = normalize_seed(InvestigationSeed(phone="55 1234 5678"))
    assert seed.phone == "5512345678"
    assert not validate_seed(seed)
    assert username_search_candidates(seed) == []


def test_requires_supported_identifier():
    assert validate_seed(normalize_seed(InvestigationSeed(email="legacy@example.com")))
