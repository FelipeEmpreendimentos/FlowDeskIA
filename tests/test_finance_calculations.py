from decimal import Decimal

import pytest

from app.services.finance import calcular_fechamento


def test_fechamento_pendente_sem_pagamento() -> None:
    calculo = calcular_fechamento(valor_original="100.00")

    assert calculo.valor_final == Decimal("100.00")
    assert calculo.valor_recebido == Decimal("0.00")
    assert calculo.valor_pendente == Decimal("100.00")
    assert calculo.status == "PENDENTE"


def test_desconto_percentual_e_pagamento_parcial() -> None:
    calculo = calcular_fechamento(
        valor_original="100.00",
        desconto_tipo="PERCENTUAL",
        desconto_informado="10",
        pagamentos=["40.00"],
    )

    assert calculo.desconto_valor == Decimal("10.00")
    assert calculo.valor_final == Decimal("90.00")
    assert calculo.valor_recebido == Decimal("40.00")
    assert calculo.valor_pendente == Decimal("50.00")
    assert calculo.status == "PARCIAL"


def test_multiplos_pagamentos_quitam_atendimento() -> None:
    calculo = calcular_fechamento(
        valor_original="89.90",
        pagamentos=["50.00", "39.90"],
    )

    assert calculo.valor_recebido == Decimal("89.90")
    assert calculo.valor_pendente == Decimal("0.00")
    assert calculo.status == "PAGO"


def test_cortesia_zerada() -> None:
    calculo = calcular_fechamento(
        valor_original="89.90",
        cortesia=True,
    )

    assert calculo.desconto_valor == Decimal("89.90")
    assert calculo.valor_final == Decimal("0.00")
    assert calculo.status == "CORTESIA"


def test_rejeita_pagamento_acima_do_total() -> None:
    with pytest.raises(ValueError, match="ultrapassar"):
        calcular_fechamento(
            valor_original="100.00",
            pagamentos=["100.01"],
        )


def test_rejeita_pagamento_em_cortesia() -> None:
    with pytest.raises(ValueError, match="cortesia"):
        calcular_fechamento(
            valor_original="100.00",
            pagamentos=["1.00"],
            cortesia=True,
        )
