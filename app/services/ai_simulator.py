from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import RemetenteMensagem
from app.models.models import (
    Cliente,
    ConfigIA,
    Conversa,
    Empresa,
    MemoriaIA,
    Mensagem,
    Veiculo,
)
from app.services.ai_conversation import (
    AIContext,
    AIConversationStateError,
    MAX_MEMORIES,
    MAX_RECENT_MESSAGES,
    MAX_VEHICLES,
    _active_services,
    _base_instructions,
    _company_lines,
    _service_lines,
)


def _speaker_label(remetente: RemetenteMensagem) -> str:
    if remetente == RemetenteMensagem.CLIENTE:
        return "CLIENTE"
    if remetente == RemetenteMensagem.IA:
        return "ASSISTENTE IA"
    return "ATENDENTE HUMANO"


def _vehicle_lines(veiculos: list[Veiculo]) -> list[str]:
    lines: list[str] = []
    for item in veiculos:
        nome = " ".join(part for part in [item.marca, item.modelo] if part).strip()
        nome = nome or item.apelido or "Veículo"
        extras: list[str] = []
        if item.tipo_veiculo:
            extras.append(f"tipo {item.tipo_veiculo}")
        if item.ano:
            extras.append(str(item.ano))
        if item.cor:
            extras.append(item.cor)
        if item.apelido and item.apelido != nome:
            extras.append(f"apelido {item.apelido}")
        if item.observacoes and item.observacoes.strip():
            extras.append(f"observações: {item.observacoes.strip()}")
        lines.append("- " + nome + (f" ({', '.join(extras)})" if extras else ""))
    return lines or ["- Nenhum veículo cadastrado."]


def _real_recent_history(
    db: Session,
    *,
    empresa_id: int,
    cliente_id: int,
    limit: int = 12,
) -> list[str]:
    rows = list(
        db.execute(
            select(Mensagem.remetente, Mensagem.conteudo)
            .join(Conversa, Conversa.id == Mensagem.conversa_id)
            .where(
                Conversa.empresa_id == empresa_id,
                Conversa.cliente_id == cliente_id,
            )
            .order_by(Mensagem.data_envio.desc(), Mensagem.id.desc())
            .limit(limit)
        ).all()
    )
    rows.reverse()
    return [
        f"{_speaker_label(remetente)}: {conteudo.strip()}"
        for remetente, conteudo in rows
        if conteudo and conteudo.strip()
    ]


def build_real_customer_simulator_context(
    db: Session,
    *,
    empresa_id: int,
    cliente_id: int,
    transcript: list[tuple[str, str]],
) -> AIContext:
    """Monta o laboratório usando exatamente o cadastro real do cliente.

    O cliente, seus veículos, memórias e histórico recente são somente lidos.
    O simulador não cria Conversa/Mensagem e não altera o cadastro real.
    """
    empresa = db.scalar(select(Empresa).where(Empresa.id == empresa_id))
    cliente = db.scalar(
        select(Cliente).where(
            Cliente.id == cliente_id,
            Cliente.empresa_id == empresa_id,
        )
    )
    if empresa is None or cliente is None:
        raise AIConversationStateError(
            "Empresa ou cliente não está disponível para esta simulação."
        )

    config = db.scalar(select(ConfigIA).where(ConfigIA.empresa_id == empresa_id))
    servicos = _active_services(db, empresa_id)
    veiculos = list(
        db.scalars(
            select(Veiculo)
            .where(Veiculo.cliente_id == cliente_id)
            .order_by(Veiculo.created_at.desc())
            .limit(MAX_VEHICLES)
        )
    )
    memorias = list(
        db.scalars(
            select(MemoriaIA)
            .where(
                MemoriaIA.empresa_id == empresa_id,
                MemoriaIA.cliente_id == cliente_id,
            )
            .order_by(MemoriaIA.updated_at.desc())
            .limit(MAX_MEMORIES)
        )
    )

    memory_lines = [
        f"- {item.categoria or 'geral'}: {item.informacao.strip()}"
        for item in memorias
        if item.informacao and item.informacao.strip()
    ] or ["- Nenhuma memória registrada para este cliente."]

    real_history = _real_recent_history(
        db,
        empresa_id=empresa_id,
        cliente_id=cliente_id,
    )
    simulator_history = [
        f"{speaker}: {text.strip()}"
        for speaker, text in transcript[-MAX_RECENT_MESSAGES:]
        if text and text.strip()
    ]

    input_text = "\n".join(
        [
            "CONTEXTO DA EMPRESA",
            *_company_lines(empresa),
            "",
            "SERVIÇOS ATIVOS",
            *_service_lines(servicos),
            "",
            "CLIENTE REAL SELECIONADO",
            f"Nome: {cliente.nome}",
            f"Observações úteis: {cliente.observacoes.strip() if cliente.observacoes else 'nenhuma'}",
            "",
            "VEÍCULOS REAIS DO CLIENTE",
            *_vehicle_lines(veiculos),
            "",
            "MEMÓRIAS REAIS DE ATENDIMENTO",
            *memory_lines,
            "",
            "HISTÓRICO REAL RECENTE DO CLIENTE (somente contexto)",
            *(real_history or ["Nenhuma mensagem real anterior registrada."]),
            "",
            "CONVERSA ATUAL DO WHATSAPP SIMULADO",
            *(simulator_history or ["Nenhuma mensagem de teste ainda."]),
            "",
            "Responda agora à última mensagem do CLIENTE como se ela tivesse acabado de chegar pelo WhatsApp real.",
        ]
    )

    return AIContext(
        instructions=_base_instructions(
            empresa,
            config,
            simulated_whatsapp=True,
        ),
        input_text=input_text,
        model=settings.openai_model,
    )
