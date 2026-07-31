from scripts.setup_engagement import aplicar_estrutura as aplicar_engagement
from scripts.setup_financeiro import aplicar_estrutura as aplicar_financeiro
from scripts.setup_super_admin import (
    aplicar_estrutura as aplicar_super_admin,
    criar_planos_padrao,
    sincronizar_empresas_existentes,
)


def main() -> None:
    aplicar_super_admin()
    criar_planos_padrao()
    sincronizar_empresas_existentes()
    aplicar_financeiro()
    aplicar_engagement()

    print("Estrutura da versão de lançamento preparada com sucesso.")
    print("Módulos: Super Admin, planos, financeiro, onboarding e notificações.")


if __name__ == "__main__":
    main()
