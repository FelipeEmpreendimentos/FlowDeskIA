import re

from fastapi import HTTPException, status


def normalize_brazilian_mobile(
    value: str | None,
    *,
    field_label: str = "Telefone",
) -> str | None:
    """Normaliza celular brasileiro para DDD + 9 dígitos (11 números)."""
    if value is None:
        return None

    digits = re.sub(r"\D", "", value)
    if not digits:
        return None

    if len(digits) != 11 or digits[2] != "9":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{field_label} deve conter DDD + celular com 9 dígitos, por exemplo (46) 99999-9999.",
        )

    return digits
