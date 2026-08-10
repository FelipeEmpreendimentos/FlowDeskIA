from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session


def reports_use_finance(db: Session, empresa_id: int) -> bool:
    """Retorna a origem configurada para o faturamento dos relatórios.

    True preserva o comportamento histórico: os relatórios usam o Financeiro.
    Se a estrutura ainda não tiver sido aplicada, também assume True para não
    alterar empresas existentes antes da migração.
    """
    try:
        value = db.execute(
            text(
                """
                SELECT usar_financeiro
                FROM configuracoes_relatorios
                WHERE empresa_id = :empresa_id
                """
            ),
            {"empresa_id": empresa_id},
        ).scalar_one_or_none()
    except ProgrammingError:
        db.rollback()
        return True

    return True if value is None else bool(value)


def set_reports_use_finance(
    db: Session,
    *,
    empresa_id: int,
    usar_financeiro: bool,
) -> bool:
    db.execute(
        text(
            """
            INSERT INTO configuracoes_relatorios (
                empresa_id,
                usar_financeiro,
                updated_at
            )
            VALUES (:empresa_id, :usar_financeiro, NOW())
            ON CONFLICT (empresa_id)
            DO UPDATE SET
                usar_financeiro = EXCLUDED.usar_financeiro,
                updated_at = NOW()
            """
        ),
        {
            "empresa_id": empresa_id,
            "usar_financeiro": usar_financeiro,
        },
    )
    db.commit()
    return usar_financeiro
