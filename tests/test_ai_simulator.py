from datetime import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from app.core.security import create_simulator_access_token, decode_access_token
from app.services.ai_conversation import build_simulator_ai_context


def test_simulator_token_is_bound_to_company() -> None:
    token, expires_in = create_simulator_access_token(
        user_id=9,
        empresa_id=4,
        days=1,
    )

    payload = decode_access_token(token)

    assert expires_in == 24 * 60 * 60
    assert payload["kind"] == "ai_simulator"
    assert payload["sub"] == "9"
    assert payload["empresa_id"] == 4
    assert payload["jti"]


def test_simulator_context_uses_company_data_without_real_customer() -> None:
    db = Mock()
    empresa = SimpleNamespace(
        id=4,
        nome="Empresa Teste",
        cidade="Pato Branco",
        estado="PR",
        timezone="America/Sao_Paulo",
        horario_abertura=time(8, 0),
        horario_fechamento=time(18, 0),
        ativo=True,
    )
    config = SimpleNamespace(
        nome_assistente="Lia",
        prompt="Seja objetiva e cordial.",
    )
    servico = SimpleNamespace(
        nome="Lavagem completa",
        preco=Decimal("120.00"),
        duracao_minutos=90,
        descricao="Interna e externa.",
        adicional_por_tipo_ativo=False,
        adicionais=[],
    )

    db.scalar.side_effect = [empresa, config]
    db.scalars.side_effect = [[servico]]

    context = build_simulator_ai_context(
        db,
        empresa_id=4,
        customer_name="Cliente de teste",
        vehicle_type="SEDAN",
        vehicle_description="Honda Civic 2022",
        customer_notes="Prefere manhã.",
        transcript=[
            ("ASSISTENTE IA", "Olá! Como posso ajudar?"),
            ("CLIENTE", "Quanto custa a lavagem completa?"),
        ],
    )

    assert "Empresa Teste" in context.input_text
    assert "Lavagem completa: R$ 120,00" in context.input_text
    assert "Cliente de teste" in context.input_text
    assert "SEDAN" in context.input_text
    assert "Honda Civic 2022" in context.input_text
    assert "Quanto custa a lavagem completa?" in context.input_text
    assert "WhatsApp real" in context.instructions
    assert "Seja objetiva e cordial." in context.instructions
    assert "NÃO possui ferramenta" in context.instructions
