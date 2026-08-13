from fastapi import APIRouter

from app.api.routes import (
    acessos,
    administrativo,
    agenda,
    atividades,
    auth,
    bloqueios,
    chat_interno,
    clientes,
    configuracao_agenda,
    configuracao_relatorios,
    configuracoes,
    conversas,
    empresas,
    financeiro,
    financeiro_permissoes,
    horarios,
    ia,
    notificacoes,
    onboarding,
    plano_empresa,
    preferencias_notificacoes,
    relatorios,
    servicos,
    smart_agenda,
    super_admin,
    super_admin_dashboard,
    system,
    usuarios,
    veiculos,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(super_admin.router)
api_router.include_router(super_admin_dashboard.router)
api_router.include_router(empresas.router)
api_router.include_router(acessos.router)
api_router.include_router(usuarios.router)
api_router.include_router(clientes.router)
api_router.include_router(veiculos.router)
api_router.include_router(servicos.router)
# A agenda inteligente precisa ser registrada antes da rota legada de
# disponibilidade para centralizar a regra de distribuição automática.
api_router.include_router(smart_agenda.router)
api_router.include_router(agenda.router)
api_router.include_router(configuracao_agenda.router)
api_router.include_router(configuracao_relatorios.router)
api_router.include_router(financeiro_permissoes.router)
api_router.include_router(financeiro.router)
api_router.include_router(relatorios.router)
api_router.include_router(plano_empresa.router)
api_router.include_router(atividades.router)
api_router.include_router(onboarding.router)
api_router.include_router(preferencias_notificacoes.router)
api_router.include_router(horarios.router)
api_router.include_router(bloqueios.router)
api_router.include_router(conversas.router)
api_router.include_router(ia.router)
api_router.include_router(chat_interno.router)
api_router.include_router(configuracoes.router)
api_router.include_router(notificacoes.router)
api_router.include_router(administrativo.router)
