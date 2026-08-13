from app.core.security import create_refresh_token, decode_access_token
from app.main import app
from app.schemas.auth import LoginRequest


def test_login_nao_mantem_conectado_por_padrao() -> None:
    data = LoginRequest(
        empresa_id=1,
        email="usuario@empresa.com",
        senha="senha-segura",
    )
    assert data.manter_conectado is False


def test_login_aceita_manter_conectado() -> None:
    data = LoginRequest(
        empresa_id=1,
        email="usuario@empresa.com",
        senha="senha-segura",
        manter_conectado=True,
    )
    assert data.manter_conectado is True


def test_refresh_token_dura_trinta_dias_e_tem_tipo_proprio() -> None:
    token, expires_in = create_refresh_token(
        user_id=10,
        empresa_id=20,
        days=30,
    )
    payload = decode_access_token(token)

    assert expires_in == 30 * 24 * 60 * 60
    assert payload["kind"] == "company_refresh"
    assert payload["sub"] == "10"
    assert payload["empresa_id"] == 20


def test_rotas_de_renovacao_e_logout_estao_registradas() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/auth/refresh" in paths
    assert "/api/v1/auth/logout" in paths
