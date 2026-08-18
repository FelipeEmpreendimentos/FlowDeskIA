from __future__ import annotations

import re

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.security import decode_access_token
from app.database.database import SessionLocal
from app.models.models import Usuario
from app.services.attendance_presence import require_can_reply


HUMAN_MESSAGE_PATH = re.compile(r"^/api/v1/conversas/\d+/mensagens/?$")


async def attendance_presence_guard(request: Request, call_next):
    """Bloqueia resposta humana quando o usuário está efetivamente Offline.

    A regra é aplicada somente ao envio manual de mensagens para não adicionar
    um round trip de presença nas demais rotas do sistema.
    """

    if request.method == "POST" and HUMAN_MESSAGE_PATH.match(request.url.path):
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
            try:
                payload = decode_access_token(token)
                if payload.get("kind", "company_user") == "company_user":
                    user_id = int(payload["sub"])
                    empresa_id = int(payload["empresa_id"])
                    with SessionLocal() as db:
                        user = db.scalar(
                            select(Usuario).where(
                                Usuario.id == user_id,
                                Usuario.empresa_id == empresa_id,
                                Usuario.ativo.is_(True),
                            )
                        )
                        if user is not None:
                            try:
                                require_can_reply(db, user)
                            except Exception as exc:
                                detail = getattr(exc, "detail", None)
                                if detail:
                                    return JSONResponse(
                                        status_code=getattr(exc, "status_code", 409),
                                        content={"detail": str(detail)},
                                    )
            except (ValueError, KeyError, TypeError):
                # O middleware de autenticação/rota devolverá o erro canônico.
                pass

    return await call_next(request)
