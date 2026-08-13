from fastapi import HTTPException, status

from app.models.enums import CargoUsuario
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
    """Remove campos estruturais reenviados sem alteração pelo formulário."""

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
    """Permite ao funcionário operar integralmente apenas a própria agenda.

    A permissão Visualizar Agenda representa o escopo pessoal: o funcionário
    pode editar dados, alterar status e cancelar os próprios atendimentos, mas
    nunca assumir, remover ou transferir o responsável. Gerenciar Agenda eleva
    a requisição para o escopo global e não passa por estas restrições.
    """

    if is_management(user):
        return

    if appointment.funcionario_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você só pode alterar agendamentos atribuídos a você.",
        )

    _remove_unchanged_appointment_fields(appointment, values)

    if "funcionario_id" in values:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Para escolher ou trocar o funcionário é necessário Gerenciar Agenda.",
        )
