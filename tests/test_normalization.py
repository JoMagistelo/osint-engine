from osint_engine.models import InvestigationSeed
from osint_engine.normalization import conservative_alias_candidates, normalize_seed, validate_seed


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


def test_alias_candidate_is_hypothesis_source_only():
    seed = InvestigationSeed(email="nombre.apellido@example.com")
    assert conservative_alias_candidates(seed) == ["nombre.apellido"]


def test_requires_identifier():
    assert validate_seed(InvestigationSeed())
