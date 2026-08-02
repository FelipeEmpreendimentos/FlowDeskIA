from scripts.setup_agenda_settings import aplicar_estrutura as aplicar_agenda_settings
from scripts.setup_chat_interno import aplicar_estrutura as aplicar_chat_interno
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
    aplicar_chat_interno()
    aplicar_agenda_settings()

    print("Estrutura da versão de lançamento preparada com sucesso.")
    print(
        "Módulos: Super Admin, planos, financeiro, onboarding, notificações, chat interno e configurações da agenda."
    )


if __name__ == "__main__":
    main()
