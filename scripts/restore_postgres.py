import argparse
import os
import shutil
import subprocess
from pathlib import Path

from app.core.config import settings


def _executavel(nome: str) -> str:
    caminho = shutil.which(nome)
    if not caminho:
        raise RuntimeError(
            f"O executável {nome} não foi encontrado. Instale as ferramentas do PostgreSQL e tente novamente."
        )
    return caminho


def restaurar(arquivo: Path) -> None:
    if not arquivo.exists() or not arquivo.is_file():
        raise FileNotFoundError(f"Backup não encontrado: {arquivo}")
    if arquivo.stat().st_size == 0:
        raise RuntimeError("O backup informado está vazio.")

    ambiente = os.environ.copy()
    ambiente["PGPASSWORD"] = settings.db_password
    comando = [
        _executavel("pg_restore"),
        "--host",
        settings.db_host,
        "--port",
        str(settings.db_port),
        "--username",
        settings.db_user,
        "--dbname",
        settings.db_name,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        str(arquivo),
    ]
    resultado = subprocess.run(
        comando,
        env=ambiente,
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        raise RuntimeError(
            "A restauração não foi concluída. "
            + (resultado.stderr.strip() or "Erro não informado pelo pg_restore.")
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restaura um backup do FlowDeskIA no banco configurado no .env."
    )
    parser.add_argument("--arquivo", required=True, help="Arquivo .dump a restaurar.")
    parser.add_argument(
        "--confirmar",
        required=True,
        help="Digite RESTAURAR para confirmar a substituição dos dados.",
    )
    args = parser.parse_args()

    if args.confirmar != "RESTAURAR":
        raise RuntimeError(
            "Restauração cancelada. Use --confirmar RESTAURAR somente após conferir o banco e o arquivo."
        )

    arquivo = Path(args.arquivo).expanduser().resolve()
    restaurar(arquivo)
    print(f"Restauração concluída a partir de: {arquivo}")


if __name__ == "__main__":
    main()
