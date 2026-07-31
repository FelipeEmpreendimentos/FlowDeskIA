import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import PROJECT_ROOT, settings


def _executavel(nome: str) -> str:
    caminho = shutil.which(nome)
    if not caminho:
        raise RuntimeError(
            f"O executável {nome} não foi encontrado. Instale as ferramentas do PostgreSQL e tente novamente."
        )
    return caminho


def _remover_antigos(diretorio: Path, reter_dias: int) -> None:
    if reter_dias <= 0:
        return
    limite = datetime.now(timezone.utc) - timedelta(days=reter_dias)
    for arquivo in diretorio.glob("flowdesk_*"):
        if not arquivo.is_file():
            continue
        alterado = datetime.fromtimestamp(arquivo.stat().st_mtime, tz=timezone.utc)
        if alterado < limite:
            arquivo.unlink(missing_ok=True)


def criar_backup(destino: Path, reter_dias: int, incluir_uploads: bool) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    arquivo_banco = destino / f"flowdesk_{timestamp}.dump"

    ambiente = os.environ.copy()
    ambiente["PGPASSWORD"] = settings.db_password
    comando = [
        _executavel("pg_dump"),
        "--host",
        settings.db_host,
        "--port",
        str(settings.db_port),
        "--username",
        settings.db_user,
        "--dbname",
        settings.db_name,
        "--format",
        "custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(arquivo_banco),
    ]
    resultado = subprocess.run(
        comando,
        env=ambiente,
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        arquivo_banco.unlink(missing_ok=True)
        raise RuntimeError(
            "O PostgreSQL não conseguiu criar o backup. "
            + (resultado.stderr.strip() or "Erro não informado pelo pg_dump.")
        )
    if not arquivo_banco.exists() or arquivo_banco.stat().st_size == 0:
        raise RuntimeError("O arquivo de backup foi criado vazio.")

    arquivo_uploads: Path | None = None
    uploads = PROJECT_ROOT / "uploads"
    if incluir_uploads and uploads.exists():
        base_zip = destino / f"flowdesk_{timestamp}_uploads"
        arquivo_uploads = Path(
            shutil.make_archive(str(base_zip), "zip", root_dir=uploads)
        )

    manifesto = destino / f"flowdesk_{timestamp}.json"
    manifesto.write_text(
        json.dumps(
            {
                "criado_em": datetime.now(timezone.utc).isoformat(),
                "banco": settings.db_name,
                "host": settings.db_host,
                "arquivo_banco": arquivo_banco.name,
                "tamanho_banco_bytes": arquivo_banco.stat().st_size,
                "arquivo_uploads": arquivo_uploads.name if arquivo_uploads else None,
                "tamanho_uploads_bytes": (
                    arquivo_uploads.stat().st_size if arquivo_uploads else 0
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _remover_antigos(destino, reter_dias)
    return arquivo_banco


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria backup do FlowDeskIA.")
    parser.add_argument(
        "--destino",
        default=str(PROJECT_ROOT / "backups"),
        help="Pasta onde os arquivos serão salvos.",
    )
    parser.add_argument(
        "--reter-dias",
        type=int,
        default=30,
        help="Remove arquivos mais antigos que esta quantidade de dias.",
    )
    parser.add_argument(
        "--sem-uploads",
        action="store_true",
        help="Não inclui a pasta de uploads no backup.",
    )
    args = parser.parse_args()
    arquivo = criar_backup(
        Path(args.destino).expanduser().resolve(),
        args.reter_dias,
        not args.sem_uploads,
    )
    print(f"Backup concluído: {arquivo}")


if __name__ == "__main__":
    main()
