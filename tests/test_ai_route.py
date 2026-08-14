from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.api.routes import ia as ia_routes
from app.models.enums import CargoUsuario, StatusConversa
from app.services.ai_conversation import AINotConfiguredError


def _user():
    return SimpleNamespace(id=5, empresa_id=2, cargo=CargoUsuario.ADMIN)


def _conversation():
    return SimpleNamespace(
        id=31,
        empresa_id=2,
        responsavel_id=None,
        status=StatusConversa.ABERTA,
        ia_ativa=True,
    )


def test_endpoint_gera_e_confirma_resposta_da_ia() -> None:
    db = Mock()
    user = _user()
    conversation = _conversation()
    message = SimpleNamespace(id=90, conteudo="Olá! Como posso ajudar?")

    with (
        patch.object(
            ia_routes,
            "_get_conversation_for_update",
            return_value=conversation,
        ) as get_locked,
        patch.object(ia_routes, "_ensure_conversation_access") as ensure_access,
        patch.object(ia_routes, "generate_ai_reply", return_value=message) as generate,
        patch.object(
            ia_routes,
            "commit_or_conflict",
            side_effect=lambda _db, item: item,
        ) as commit,
    ):
        result = ia_routes.responder_conversa_com_ia(
            conversation.id,
            current_user=user,
            db=db,
        )

    assert result is message
    get_locked.assert_called_once_with(
        db,
        empresa_id=user.empresa_id,
        conversa_id=conversation.id,
    )
    ensure_access.assert_called_once_with(conversation, user)
    generate.assert_called_once_with(db, conversation)
    commit.assert_called_once_with(db, message)


def test_endpoint_retorna_503_quando_openai_nao_esta_configurada() -> None:
    db = Mock()
    user = _user()
    conversation = _conversation()

    with (
        patch.object(
            ia_routes,
            "_get_conversation_for_update",
            return_value=conversation,
        ),
        patch.object(ia_routes, "_ensure_conversation_access"),
        patch.object(
            ia_routes,
            "generate_ai_reply",
            side_effect=AINotConfiguredError("Configure OPENAI_API_KEY."),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            ia_routes.responder_conversa_com_ia(
                conversation.id,
                current_user=user,
                db=db,
            )

    assert exc_info.value.status_code == 503
    assert "OPENAI_API_KEY" in str(exc_info.value.detail)


def test_endpoint_nao_responde_conversa_finalizada() -> None:
    db = Mock()
    user = _user()
    conversation = _conversation()
    conversation.status = StatusConversa.FINALIZADA

    with (
        patch.object(
            ia_routes,
            "_get_conversation_for_update",
            return_value=conversation,
        ),
        patch.object(ia_routes, "_ensure_conversation_access"),
        patch.object(ia_routes, "generate_ai_reply") as generate,
    ):
        with pytest.raises(HTTPException) as exc_info:
            ia_routes.responder_conversa_com_ia(
                conversation.id,
                current_user=user,
                db=db,
            )

    assert exc_info.value.status_code == 409
    generate.assert_not_called()
