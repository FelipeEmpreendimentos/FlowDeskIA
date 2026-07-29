from fastapi import APIRouter

from app.api.routes import (
    administrativo,
    agenda,
    auth,
    bloqueios,
    clientes,
    configuracoes,
    conversas,
    empresas,
    horarios,
    notificacoes,
    servicos,
    system,
    usuarios,
    veiculos,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(empresas.router)
api_router.include_router(usuarios.router)
api_router.include_router(clientes.router)
api_router.include_router(veiculos.router)
api_router.include_router(servicos.router)
api_router.include_router(agenda.router)
api_router.include_router(horarios.router)
api_router.include_router(bloqueios.router)
api_router.include_router(conversas.router)
api_router.include_router(configuracoes.router)
api_router.include_router(notificacoes.router)
api_router.include_router(administrativo.router)
