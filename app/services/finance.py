from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


CENTAVOS = Decimal("0.01")


@dataclass(frozen=True)
class CalculoFechamento:
    valor_original: Decimal
    desconto_valor: Decimal
    valor_final: Decimal
    valor_recebido: Decimal
    valor_pendente: Decimal
    status: str


def dinheiro(valor: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(valor or 0)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def calcular_fechamento(
    *,
    valor_original: Decimal | int | float | str,
    desconto_tipo: str | None = None,
    desconto_informado: Decimal | int | float | str | None = None,
    pagamentos: list[Decimal | int | float | str] | None = None,
    cortesia: bool = False,
) -> CalculoFechamento:
    original = dinheiro(valor_original)
    desconto = dinheiro(desconto_informado)
    recebidos = [dinheiro(valor) for valor in (pagamentos or [])]

    if original < 0:
        raise ValueError("O valor original não pode ser negativo.")

    if any(valor <= 0 for valor in recebidos):
        raise ValueError("Todo pagamento precisa ter valor maior que zero.")

    tipo = desconto_tipo.upper() if desconto_tipo else None
    if tipo not in (None, "VALOR", "PERCENTUAL"):
        raise ValueError("Tipo de desconto inválido.")

    if cortesia:
        if recebidos:
            raise ValueError("Atendimentos de cortesia não podem possuir pagamentos.")
        return CalculoFechamento(
            valor_original=original,
            desconto_valor=original,
            valor_final=dinheiro(0),
            valor_recebido=dinheiro(0),
            valor_pendente=dinheiro(0),
            status="CORTESIA",
        )

    if tipo is None:
        desconto_aplicado = dinheiro(0)
    elif tipo == "VALOR":
        if desconto > original:
            raise ValueError("O desconto não pode ser maior que o valor do atendimento.")
        desconto_aplicado = desconto
    else:
        if desconto < 0 or desconto > 100:
            raise ValueError("O desconto percentual deve ficar entre 0 e 100.")
        desconto_aplicado = dinheiro(original * desconto / Decimal("100"))

    final = dinheiro(original - desconto_aplicado)
    recebido = dinheiro(sum(recebidos, Decimal("0.00")))

    if recebido > final:
        raise ValueError("O total recebido não pode ultrapassar o valor final.")

    pendente = dinheiro(final - recebido)
    if final == 0 or pendente == 0:
        status = "PAGO"
    elif recebido > 0:
        status = "PARCIAL"
    else:
        status = "PENDENTE"

    return CalculoFechamento(
        valor_original=original,
        desconto_valor=desconto_aplicado,
        valor_final=final,
        valor_recebido=recebido,
        valor_pendente=pendente,
        status=status,
    )
