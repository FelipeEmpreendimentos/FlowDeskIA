from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import PROJECT_ROOT, settings

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Backend MVP do FlowDeskIA: autenticação, empresas, usuários, clientes, "
        "veículos, serviços, agenda, conversas e configurações."
    ),
)

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


@app.get("/", tags=["Sistema"])
def raiz() -> dict[str, str]:
    return {
        "aplicacao": settings.app_name,
        "status": "online",
        "documentacao": "/docs",
    }
