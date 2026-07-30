from fastapi import HTTPException, status

from app.models.enums import CargoUsuario, StatusAgendamento
from app.models.models import Agendamento, Usuario

MANAGEMENT_ROLES = {CargoUsuario.ADMIN, CargoUsuario.GERENTE}


def is_admin(user: Usuario) -> bool:
    return user.cargo == CargoUsuario.ADMIN


def is_management(user: Usuario) -> bool:
    return user.cargo in MANAGEMENT_ROLES


def require_admin_user(user: Usuario) -> None:
    if not is_admin(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Somente administradores podem realizar esta operação.",
        )


def require_management_user(user: Usuario) -> None:
    if not is_management(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Somente administradores e gerentes podem realizar esta operação.",
        )


def _remove_unchanged_appointment_fields(
    appointment: Agendamento,
    values: dict,
) -> None:
    """Remove campos estruturais reenviados sem alteração pelo formulário.

    A tela de edição compartilha o mesmo formulário entre gestão e funcionários.
    O navegador pode reenviar campos bloqueados com os valores originais. Esses
    campos não representam uma tentativa de alteração e podem ser ignorados com
    segurança antes da validação das permissões.
    """

    current_values = {
        "veiculo_id": appointment.veiculo_id,
        "tipo_veiculo": appointment.tipo_veiculo_cobrado,
        "servico_id": appointment.servico_id,
        "funcionario_id": appointment.funcionario_id,
        "data": appointment.data,
        "hora_inicio": appointment.hora_inicio,
        "hora_fim": appointment.hora_fim,
        "status": appointment.status,
    }

    for field, current_value in current_values.items():
        if field in values and values[field] == current_value:
            values.pop(field)


def validate_employee_appointment_update(
    user: Usuario,
    appointment: Agendamento,
    values: dict,
) -> None:
    """Valida a atuação do funcionário sem alterar o agendamento do banco.

    Funcionários visualizam toda a agenda, podem criar agendamentos e atualizar
    apenas status, observações e forma de pagamento de um atendimento próprio
    ou ainda sem responsável. Alterações estruturais continuam restritas à
    gestão.
    """

    if is_management(user):
        return

    if appointment.funcionario_id not in (None, user.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você só pode alterar agendamentos atribuídos a você.",
        )

    _remove_unchanged_appointment_fields(appointment, values)

    allowed_fields = {"status", "observacoes", "forma_pagamento"}
    forbidden_fields = set(values) - allowed_fields
    if forbidden_fields:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Funcionários podem alterar apenas status, observações e forma de pagamento.",
        )

    allowed_statuses = {
        StatusAgendamento.CONFIRMADO,
        StatusAgendamento.EM_ANDAMENTO,
        StatusAgendamento.FINALIZADO,
    }
    new_status = values.get("status")
    if new_status is not None and new_status not in allowed_statuses:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Funcionários não podem cancelar nem retornar o agendamento para pendente.",
        )
