from fastapi import HTTPException, status


def ai_not_configured() -> None:
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        (
            "O adaptador de IA ainda depende da escolha do provedor e da chave da API. "
            "O banco e a configuração da IA já estão preparados."
        ),
    )


def whatsapp_not_configured() -> None:
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        (
            "O webhook do WhatsApp depende da escolha entre Meta Cloud API ou "
            "um provedor oficial e das respectivas credenciais."
        ),
    )
