import { Link, useOutletContext } from "react-router";
import { Icon, type IconName } from "../components/Icon";
import { PageHeader } from "../components/UI";
import type { AppOutletContext, CargoUsuario } from "../types";

type ConfiguracaoGrupo = "OPERACAO" | "ADMINISTRACAO" | "SISTEMA";

interface ConfiguracaoCard {
  to?: string;
  title: string;
  description: string;
  icon: IconName;
  cargos: CargoUsuario[];
  grupo: ConfiguracaoGrupo;
  badge?: string;
  variant?: "upcoming" | "info";
}

interface GrupoConfiguracao {
  id: ConfiguracaoGrupo;
  eyebrow: string;
  title: string;
  description: string;
}

const grupos: GrupoConfiguracao[] = [
  {
    id: "OPERACAO",
    eyebrow: "Operação",
    title: "Atendimento e rotina",
    description: "Regras que afetam o atendimento e a execução do dia a dia da empresa.",
  },
  {
    id: "ADMINISTRACAO",
    eyebrow: "Administração",
    title: "Empresa e gestão",
    description: "Dados, acessos e controles usados para administrar a operação.",
  },
  {
    id: "SISTEMA",
    eyebrow: "Sistema",
    title: "Segurança e conta",
    description: "Preferências do FlowDeskIA, histórico de atividades e informações do plano.",
  },
];

const cards: ConfiguracaoCard[] = [
  {
    to: "/configuracoes/agenda",
    title: "Agenda e atendimento",
    description:
      "Defina intervalos, disponibilidade, equipes e regras usadas na distribuição automática.",
    icon: "calendar",
    cargos: ["ADMIN", "GERENTE"],
    grupo: "OPERACAO",
  },
  {
    to: "/servicos",
    title: "Serviços e equipe",
    description:
      "Gerencie serviços, preços e as pessoas habilitadas para realizar cada atendimento.",
    icon: "services",
    cargos: ["ADMIN", "GERENTE"],
    grupo: "OPERACAO",
  },
  {
    to: "/configuracoes/ia/personalizacao",
    title: "Inteligência artificial",
    description:
      "Personalize botões, perguntas e o comportamento apresentado durante o atendimento da IA.",
    icon: "bot",
    cargos: ["ADMIN", "GERENTE"],
    grupo: "OPERACAO",
    badge: "Automação",
  },
  {
    title: "WhatsApp e integrações",
    description:
      "Conecte o WhatsApp da empresa e acompanhe integrações externas usadas pelo FlowDeskIA.",
    icon: "chat",
    cargos: ["ADMIN", "GERENTE"],
    grupo: "OPERACAO",
    badge: "Em breve",
    variant: "upcoming",
  },
  {
    to: "/configuracoes/dados",
    title: "Empresa e conta",
    description:
      "Consulte os dados da empresa, altere sua senha e ajuste dados pessoais.",
    icon: "settings",
    cargos: ["ADMIN", "GERENTE", "FUNCIONARIO"],
    grupo: "ADMINISTRACAO",
  },
  {
    to: "/configuracoes/acessos",
    title: "Usuários e permissões",
    description:
      "Gerencie acessos e libere áreas específicas do sistema para cada usuário.",
    icon: "users",
    cargos: ["ADMIN"],
    grupo: "ADMINISTRACAO",
    badge: "Administrador",
  },
  {
    to: "/configuracoes/relatorios",
    title: "Financeiro e relatórios",
    description:
      "Defina a origem do faturamento e as regras usadas nos indicadores financeiros.",
    icon: "finance",
    cargos: ["ADMIN"],
    grupo: "ADMINISTRACAO",
    badge: "Administrador",
  },
  {
    title: "Notificações",
    description:
      "As notificações da operação continuam disponíveis pelo sino no topo do sistema.",
    icon: "bell",
    cargos: ["ADMIN", "GERENTE", "FUNCIONARIO"],
    grupo: "SISTEMA",
    badge: "Pelo sino",
    variant: "info",
  },
  {
    to: "/atividades",
    title: "Segurança e atividades",
    description:
      "Acompanhe acessos, alterações e ações realizadas dentro da empresa.",
    icon: "clock",
    cargos: ["ADMIN", "GERENTE"],
    grupo: "SISTEMA",
  },
  {
    to: "/plano-consumo",
    title: "Assinatura e plano",
    description:
      "Consulte o plano atual, limites disponíveis e consumo dos recursos.",
    icon: "lock",
    cargos: ["ADMIN"],
    grupo: "SISTEMA",
    badge: "Administrador",
  },
];

const cargoLabel: Record<CargoUsuario, string> = {
  ADMIN: "Administrador",
  GERENTE: "Gerente",
  FUNCIONARIO: "Funcionário",
};

export function ConfiguracoesHub() {
  const { usuario } = useOutletContext<AppOutletContext>();
  const cardsDisponiveis = cards.filter((card) =>
    card.cargos.includes(usuario.cargo),
  );
  const funcionario = usuario.cargo === "FUNCIONARIO";

  return (
    <div className="page settings-hub-page">
      <PageHeader
        eyebrow={funcionario ? "Preferências pessoais" : "Central administrativa"}
        title={funcionario ? "Minha conta" : "Configurações"}
        description={
          funcionario
            ? "Gerencie seus dados de conta e acompanhe as notificações disponíveis no sistema."
            : "Configurações organizadas por operação, administração e sistema para facilitar a gestão da empresa."
        }
      />

      <section className="settings-hub-profile" aria-label="Usuário conectado">
        <span className="settings-hub-avatar">
          {usuario.nome.charAt(0).toUpperCase()}
        </span>
        <div>
          <strong>{usuario.nome}</strong>
          <span>{usuario.email}</span>
        </div>
        <span className={`settings-hub-role settings-hub-role-${usuario.cargo.toLowerCase()}`}>
          {cargoLabel[usuario.cargo]}
        </span>
      </section>

      <div className="settings-hub-groups">
        {grupos.map((grupo) => {
          const cardsDoGrupo = cardsDisponiveis.filter(
            (card) => card.grupo === grupo.id,
          );

          if (cardsDoGrupo.length === 0) return null;

          return (
            <section className="settings-hub-section" key={grupo.id}>
              <div className="settings-hub-section-heading">
                <div>
                  <span>{grupo.eyebrow}</span>
                  <h2>{grupo.title}</h2>
                </div>
                <p>{grupo.description}</p>
              </div>

              <div className="settings-hub-grid">
                {cardsDoGrupo.map((card) => {
                  const content = (
                    <>
                      <span className="settings-hub-card-icon">
                        <Icon name={card.icon} size={23} />
                      </span>
                      <div>
                        <div className="settings-hub-card-title">
                          <h2>{card.title}</h2>
                          {card.badge && <span>{card.badge}</span>}
                        </div>
                        <p>{card.description}</p>
                      </div>
                      <span className="settings-hub-card-arrow" aria-hidden="true">
                        {card.to ? "→" : card.variant === "upcoming" ? "…" : "•"}
                      </span>
                    </>
                  );

                  if (card.to) {
                    return (
                      <Link className="settings-hub-card" to={card.to} key={card.title}>
                        {content}
                      </Link>
                    );
                  }

                  return (
                    <article
                      className={`settings-hub-card settings-hub-card-static ${
                        card.variant === "upcoming"
                          ? "settings-hub-card-upcoming"
                          : "settings-hub-card-info"
                      }`}
                      key={card.title}
                    >
                      {content}
                    </article>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
