from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.database import get_db
from app.models.ai import AICompanySettings, DEFAULT_AI_MENU, DEFAULT_AI_QUESTIONS
from app.models.enums import CargoUsuario
from app.models.models import Usuario
from app.schemas.ai_personalization import AIPersonalizationOut, AIPersonalizationPut
from app.services.audit import add_audit_log
from app.services.db_utils import commit_or_conflict


router = APIRouter(
    prefix="/configuracoes/ia-personalizacao",
    tags=["Configurações - Personalização IA"],
)


def _get_or_create(db: Session, empresa_id: int) -> AICompanySettings:
    item = db.scalar(
        select(AICompanySettings).where(AICompanySettings.empresa_id == empresa_id)
    )
    if item is None:
        item = AICompanySettings(
            empresa_id=empresa_id,
            menu_principal=[dict(entry) for entry in DEFAULT_AI_MENU],
            perguntas_basicas=dict(DEFAULT_AI_QUESTIONS),
        )
        db.add(item)
        db.flush()
    return item


def _normalized_menu(value: list[dict] | None) -> list[dict]:
    source = value or [dict(entry) for entry in DEFAULT_AI_MENU]
    by_action = {
        str(item.get("acao")): item
        for item in source
        if isinstance(item, dict) and item.get("acao")
    }
    result: list[dict] = []
    for default in DEFAULT_AI_MENU:
        saved = by_action.get(default["acao"], {})
        result.append(
            {
                "acao": default["acao"],
                "rotulo": str(saved.get("rotulo") or default["rotulo"])[:40],
                "ativo": bool(saved.get("ativo", default["ativo"])),
                "ordem": int(saved.get("ordem") or default["ordem"]),
            }
        )
    result.sort(key=lambda item: (item["ordem"], item["acao"]))
    return result


def _normalized_questions(value: dict | None) -> dict[str, str]:
    saved = value if isinstance(value, dict) else {}
    return {
        key: str(saved.get(key) or default)
        for key, default in DEFAULT_AI_QUESTIONS.items()
    }


def _out(item: AICompanySettings) -> AIPersonalizationOut:
    return AIPersonalizationOut(
        empresa_id=item.empresa_id,
        texto_menu_principal=item.texto_menu_principal,
        menu_principal=_normalized_menu(item.menu_principal),
        perguntas_basicas=_normalized_questions(item.perguntas_basicas),
    )


@router.get("", response_model=AIPersonalizationOut)
def obter_personalizacao_ia(
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> AIPersonalizationOut:
    item = _get_or_create(db, current_user.empresa_id)
    if not item.menu_principal:
        item.menu_principal = [dict(entry) for entry in DEFAULT_AI_MENU]
    if not item.perguntas_basicas:
        item.perguntas_basicas = dict(DEFAULT_AI_QUESTIONS)
    db.commit()
    return _out(item)


@router.put("", response_model=AIPersonalizationOut)
def salvar_personalizacao_ia(
    data: AIPersonalizationPut,
    current_user: Usuario = Depends(
        require_roles(CargoUsuario.ADMIN, CargoUsuario.GERENTE)
    ),
    db: Session = Depends(get_db),
) -> AIPersonalizationOut:
    item = _get_or_create(db, current_user.empresa_id)
    item.texto_menu_principal = (
        data.texto_menu_principal.strip() if data.texto_menu_principal else None
    )
    item.menu_principal = [
        {
            **entry.model_dump(),
            "rotulo": entry.rotulo.strip(),
            "ordem": (index + 1) * 10,
        }
        for index, entry in enumerate(data.menu_principal)
    ] or [dict(entry) for entry in DEFAULT_AI_MENU]
    item.perguntas_basicas = {
        key: value.strip()
        for key, value in data.perguntas_basicas.model_dump().items()
    }

    add_audit_log(
        db,
        user=current_user,
        action="ATUALIZOU_PERSONALIZACAO_IA",
        entity="ai_company_settings",
        entity_id=current_user.empresa_id,
        details={
            "menu_ativo": [
                entry["acao"] for entry in item.menu_principal if entry.get("ativo")
            ],
            "perguntas_personalizadas": sorted(item.perguntas_basicas.keys()),
        },
    )
    commit_or_conflict(db, item)
    return _out(item)
