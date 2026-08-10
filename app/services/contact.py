import re

from fastapi import HTTPException, status


def normalize_brazilian_mobile(
    value: str | None,
    *,
    field_label: str = "Telefone",
) -> str | None:
    """Normaliza contato brasileiro para DDD + número com 8 ou 9 dígitos."""
    if value is None:
        return None

    digits = re.sub(r"\D", "", value)
    if not digits:
        return None

    if len(digits) not in (10, 11):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{field_label} deve conter DDD + número com 8 ou 9 dígitos, por exemplo (46) 8888-8888 ou (46) 99999-9999.",
        )

    return digits
