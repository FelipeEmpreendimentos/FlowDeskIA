from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.api.routes import conversas as conversa_routes
from app.models.enums import StatusConversa


def _historical_conversation(conversation_id: int = 11):
    return SimpleNamespace(
        id=conversation_id,
        cliente_id=7,
        origem="WHATSAPP",
        status=StatusConversa.FINALIZADA,
        responsavel_id=3,
        ia_ativa=False,
        finalizada_em=object(),
        finalizada_por_id=3,
        resumo_finalizacao="Atendimento concluído.",
        avaliacao_nota=None,
        avaliacao_solicitada=False,
        avaliacao_token=None,
        avaliacao_enviada_em=None,
        avaliacao_comentario=None,
        avaliacao_respondida_em=None,
    )


def test_reabrir_bloqueia_quando_ja_existe_conversa_ativa() -> None:
    historica = _historical_conversation()
    existente = SimpleNamespace(id=22)
    usuario = SimpleNamespace(id=5, empresa_id=1)
    db = Mock()

    with (
        patch.object(conversa_routes, "_get", return_value=historica),
        patch.object(conversa_routes, "_ensure_access"),
        patch.object(conversa_routes, "_lock_client_conversation_scope") as lock_scope,
        patch.object(
            conversa_routes,
            "_conversa_ativa_existente",
            return_value=existente,
        ) as active_lookup,
    ):
        with pytest.raises(HTTPException) as exc_info:
            conversa_routes.reabrir_conversa(
                historica.id,
                current_user=usuario,
                db=db,
            )

    assert exc_info.value.status_code == 409
    assert "conversa #22" in str(exc_info.value.detail)
    assert historica.status == StatusConversa.FINALIZADA
    lock_scope.assert_called_once_with(
        db,
        empresa_id=usuario.empresa_id,
        cliente_id=historica.cliente_id,
    )
    active_lookup.assert_called_once_with(
        db,
        empresa_id=usuario.empresa_id,
        cliente_id=historica.cliente_id,
        origem=historica.origem,
        exclude_id=historica.id,
    )


def test_reabrir_funciona_quando_nao_existe_outra_conversa_ativa() -> None:
    historica = _historical_conversation()
    usuario = SimpleNamespace(id=5, empresa_id=1)
    db = Mock()

    with (
        patch.object(conversa_routes, "_get", return_value=historica),
        patch.object(conversa_routes, "_ensure_access"),
        patch.object(conversa_routes, "_lock_client_conversation_scope"),
        patch.object(conversa_routes, "_conversa_ativa_existente", return_value=None),
        patch.object(conversa_routes, "add_audit_log"),
        patch.object(
            conversa_routes,
            "commit_or_conflict",
            side_effect=lambda _db, item, *args, **kwargs: item,
        ),
    ):
        result = conversa_routes.reabrir_conversa(
            historica.id,
            current_user=usuario,
            db=db,
        )

    assert result is historica
    assert historica.status == StatusConversa.EM_ATENDIMENTO
    assert historica.responsavel_id == usuario.id
    assert historica.ia_ativa is False
    assert historica.finalizada_em is None
    assert historica.finalizada_por_id is None
    assert historica.resumo_finalizacao is None
