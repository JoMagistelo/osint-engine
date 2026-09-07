from osint_engine.models import InvestigationSeed
from osint_engine.normalization import (
    conservative_alias_candidates,
    normalize_seed,
    username_search_candidates,
    validate_seed,
)


def test_normalize_seed():
    seed = normalize_seed(
        InvestigationSeed(
            person_name="  José   Pérez ",
            username="@@Usuario_01",
            email=" Test@Example.COM ",
            phone="+52 (55) 1234-5678",
        )
    )
    assert seed.person_name == "José Pérez"
    assert seed.username == "Usuario_01"
    assert seed.email == "test@example.com"
    assert seed.phone == "+525512345678"
    assert not validate_seed(seed)


def test_email_local_part_is_searched_automatically():
    seed = InvestigationSeed(email="nombre.apellido@example.com", derive_aliases=False)
    plan = username_search_candidates(seed)
    assert [(item.value, item.origin) for item in plan] == [
        ("nombre.apellido", "email_local_part")
    ]


def test_explicit_username_deduplicates_email_local_part():
    seed = InvestigationSeed(
        username="nombre.apellido",
        email="nombre.apellido@example.com",
        derive_aliases=False,
    )
    plan = username_search_candidates(seed)
    assert [(item.value, item.origin) for item in plan] == [
        ("nombre.apellido", "provided_username")
    ]


def test_name_generates_basic_username_pivots_without_checkbox():
    seed = InvestigationSeed(person_name="José Rodríguez", derive_aliases=False)
    assert conservative_alias_candidates(seed) == [
        "joserodriguez",
        "jose.rodriguez",
    ]


def test_name_generates_expanded_variants_when_enabled():
    seed = InvestigationSeed(person_name="José Cruz Gómez Rodríguez", derive_aliases=True)
    values = [item.value for item in username_search_candidates(seed)]
    assert "joserodriguez" in values
    assert "jose.rodriguez" in values
    assert "jose_rodriguez" in values
    assert "jrodriguez" in values
    assert "josecruzgomezrodriguez" in values


def test_requires_identifier():
    assert validate_seed(InvestigationSeed())
