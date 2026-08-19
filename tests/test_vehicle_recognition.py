from app.services.ai_guided_autonomy import _local_vehicle_guess


def test_corsa_is_identified_as_chevrolet_hatch() -> None:
    result = _local_vehicle_guess("Corsa")

    assert result is not None
    assert result["identificavel"] is True
    assert result["marca"] == "Chevrolet"
    assert result["modelo"] == "Corsa"
    assert result["tipo_veiculo"] == "HATCH"
    assert result["confianca"] == "ALTA"


def test_corsa_with_filler_and_year_does_not_require_year() -> None:
    result = _local_vehicle_guess("meu carro é um Corsa 2008")

    assert result is not None
    assert result["modelo"] == "Corsa"
    assert result["tipo_veiculo"] == "HATCH"


def test_misspelled_corsa_is_recovered_by_fuzzy_match() -> None:
    result = _local_vehicle_guess("corssa")

    assert result is not None
    assert result["modelo"] == "Corsa"
    assert result["tipo_veiculo"] == "HATCH"


def test_corsa_sedan_qualifier_is_respected() -> None:
    result = _local_vehicle_guess("Corsa Sedan")

    assert result is not None
    assert result["modelo"] == "Corsa"
    assert result["tipo_veiculo"] == "SEDAN"


def test_classic_is_treated_as_sedan() -> None:
    result = _local_vehicle_guess("Classic")

    assert result is not None
    assert result["marca"] == "Chevrolet"
    assert result["tipo_veiculo"] == "SEDAN"
