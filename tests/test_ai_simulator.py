from datetime import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from app.models.enums import RemetenteMensagem
from app.services.ai_simulator import build_real_customer_simulator_context


def test_super_admin_simulator_uses_real_customer_context() -> None:
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
    cliente = SimpleNamespace(
        id=21,
        empresa_id=4,
        nome="Felipe Cliente",
        observacoes="Prefere atendimento pela manhã.",
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
    veiculo = SimpleNamespace(
        marca="Honda",
        modelo="Civic",
        tipo_veiculo="SEDAN",
        ano=2022,
        cor="Preto",
        apelido=None,
        observacoes="Cuidado com o banco traseiro.",
        placa="ABC1D23",
    )
    memoria = SimpleNamespace(
        categoria="preferencia",
        informacao="Cliente prefere horários pela manhã.",
    )

    db.scalar.side_effect = [empresa, cliente, config]
    db.scalars.side_effect = [[servico], [veiculo], [memoria]]
    db.execute.return_value.all.return_value = [
        (RemetenteMensagem.CLIENTE, "Já fiz uma lavagem aí antes."),
    ]

    context = build_real_customer_simulator_context(
        db,
        empresa_id=4,
        cliente_id=21,
        transcript=[
            ("ASSISTENTE IA", "Olá! Como posso ajudar?"),
            ("CLIENTE", "Quanto custa a lavagem completa para o meu carro?"),
        ],
    )

    assert "Empresa Teste" in context.input_text
    assert "Lavagem completa: R$ 120,00" in context.input_text
    assert "Felipe Cliente" in context.input_text
    assert "Honda Civic" in context.input_text
    assert "tipo SEDAN" in context.input_text
    assert "Cliente prefere horários pela manhã." in context.input_text
    assert "Já fiz uma lavagem aí antes." in context.input_text
    assert "Quanto custa a lavagem completa para o meu carro?" in context.input_text
    assert "ABC1D23" not in context.input_text
    assert "WhatsApp real" in context.instructions
    assert "Seja objetiva e cordial." in context.instructions
    assert "NÃO possui ferramenta" in context.instructions
