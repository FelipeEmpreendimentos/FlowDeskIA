from datetime import date, time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.permissions import validate_employee_appointment_update
from app.models.enums import CargoUsuario, StatusAgendamento


def _user(user_id: int = 7):
    return SimpleNamespace(id=user_id, cargo=CargoUsuario.FUNCIONARIO)


def _appointment(employee_id: int = 7):
    return SimpleNamespace(
        veiculo_id=1,
        tipo_veiculo_cobrado="HATCH",
        servico_id=2,
        funcionario_id=employee_id,
        data=date(2026, 8, 10),
        hora_inicio=time(9, 0),
        hora_fim=time(10, 0),
        status=StatusAgendamento.PENDENTE,
    )


def test_visualizar_agenda_permite_editar_o_proprio_agendamento():
    user = _user()
    appointment = _appointment()
    values = {
        "funcionario_id": user.id,
        "data": date(2026, 8, 11),
        "status": StatusAgendamento.CANCELADO,
    }

    validate_employee_appointment_update(user, appointment, values)

    assert "funcionario_id" not in values
    assert values["data"] == date(2026, 8, 11)
    assert values["status"] == StatusAgendamento.CANCELADO


def test_visualizar_agenda_nao_permite_editar_agendamento_de_outro_funcionario():
    with pytest.raises(HTTPException) as exc_info:
        validate_employee_appointment_update(
            _user(user_id=7),
            _appointment(employee_id=8),
            {"observacoes": "Atualização"},
        )

    assert exc_info.value.status_code == 403


def test_visualizar_agenda_nao_permite_trocar_o_funcionario():
    with pytest.raises(HTTPException) as exc_info:
        validate_employee_appointment_update(
            _user(user_id=7),
            _appointment(employee_id=7),
            {"funcionario_id": 8},
        )

    assert exc_info.value.status_code == 403
