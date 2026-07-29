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


def validate_employee_appointment_update(
    user: Usuario,
    appointment: Agendamento,
    values: dict,
) -> None:
    """Valida a atuação do funcionário sem alterar o objeto do banco.

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
