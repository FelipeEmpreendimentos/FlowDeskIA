import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import PROJECT_ROOT, settings
from app.database.database import warm_database_pool
from app.middleware.attendance_presence import attendance_presence_guard
from app.middleware.observability import observability_middleware
from app.middleware.plan_access import plan_access_middleware
from scripts.bootstrap_company_user import aplicar_bootstrap as aplicar_bootstrap_usuario_empresa
from scripts.setup_ai_v2 import aplicar_estrutura as aplicar_ai_v2
from scripts.setup_attendance_presence import aplicar_estrutura as aplicar_presenca_atendimento


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("flowdesk.startup")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Backend do FlowDeskIA: autenticação, empresas, usuários, clientes, "
        "veículos, serviços, agenda, financeiro, relatórios, conversas, planos e Super Admin."
    ),
)

app.middleware("http")(observability_middleware)
app.middleware("http")(plan_access_middleware)
app.middleware("http")(attendance_presence_guard)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploads_dir = PROJECT_ROOT / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

app.include_router(api_router)


@app.on_event("startup")
def preparar_runtime() -> None:
    try:
        if aplicar_bootstrap_usuario_empresa():
            logger.info("company_user_bootstrap_applied")
    except Exception:
        logger.exception("company_user_bootstrap_failed")
        raise

    try:
        aplicar_ai_v2()
        logger.info("ai_v2_schema_ready")
    except Exception:
        logger.exception("ai_v2_schema_setup_failed")
        raise

    try:
        aplicar_presenca_atendimento()
        logger.info("attendance_presence_schema_ready")
    except Exception:
        logger.exception("attendance_presence_schema_setup_failed")
        raise

    try:
        warmed = warm_database_pool()
        logger.info("database_pool_warmed connections=%s", warmed)
    except Exception:
        logger.exception("database_pool_warmup_failed")


@app.get("/", tags=["Sistema"])
def raiz() -> dict[str, str]:
    return {
        "aplicacao": settings.app_name,
        "status": "online",
        "documentacao": "/docs",
    }
