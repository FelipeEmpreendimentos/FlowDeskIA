from fastapi import APIRouter

from app.api.routes import (
    administrativo,
    agenda,
    atividades,
    auth,
    bloqueios,
    clientes,
    configuracoes,
    conversas,
    empresas,
    financeiro,
    horarios,
    notificacoes,
    onboarding,
    plano_empresa,
    preferencias_notificacoes,
    relatorios,
    servicos,
    super_admin,
    system,
    usuarios,
    veiculos,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(super_admin.router)
api_router.include_router(empresas.router)
api_router.include_router(usuarios.router)
api_router.include_router(clientes.router)
api_router.include_router(veiculos.router)
api_router.include_router(servicos.router)
api_router.include_router(agenda.router)
api_router.include_router(financeiro.router)
api_router.include_router(relatorios.router)
api_router.include_router(plano_empresa.router)
api_router.include_router(atividades.router)
api_router.include_router(onboarding.router)
api_router.include_router(preferencias_notificacoes.router)
api_router.include_router(horarios.router)
api_router.include_router(bloqueios.router)
api_router.include_router(conversas.router)
api_router.include_router(configuracoes.router)
api_router.include_router(notificacoes.router)
api_router.include_router(administrativo.router)
