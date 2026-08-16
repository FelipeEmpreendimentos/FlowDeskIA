import { Link, useOutletContext } from "react-router";
import { Icon, type IconName } from "../components/Icon";
import { PageHeader } from "../components/UI";
import type { AppOutletContext, CargoUsuario } from "../types";

interface ConfiguracaoCard {
  to: string;
  title: string;
  description: string;
  icon: IconName;
  cargos: CargoUsuario[];
  badge?: string;
}

const cards: ConfiguracaoCard[] = [
  {
    to: "/configuracoes/dados",
    title: "Empresa e conta",
    description:
      "Consulte os dados da empresa, altere sua senha e ajuste dados pessoais.",
    icon: "settings",
    cargos: ["ADMIN", "GERENTE", "FUNCIONARIO"],
  },
  {
    to: "/configuracoes/agenda",
    title: "Agenda",
    description:
      "Defina intervalos, equipes por serviço e regras usadas na distribuição automática.",
    icon: "calendar",
    cargos: ["ADMIN", "GERENTE"],
  },
  {
    to: "/configuracoes/simulador-ia",
    title: "Simulador de IA",
    description:
      "Gere um link privado e teste a IA em um chat que reproduz a experiência de atendimento pelo WhatsApp.",
    icon: "bot",
    cargos: ["ADMIN", "GERENTE"],
    badge: "Laboratório",
  },
  {
    to: "/configuracoes/relatorios",
    title: "Relatórios e financeiro",
    description:
      "Escolha se o faturamento vem do Financeiro ou diretamente dos agendamentos finalizados.",
    icon: "finance",
    cargos: ["ADMIN"],
    badge: "Administrador",
  },
  {
    to: "/configuracoes/acessos",
    title: "Módulos e permissões",
    description:
      "Ative áreas da empresa e libere acessos específicos para cada usuário.",
    icon: "lock",
    cargos: ["ADMIN"],
    badge: "Administrador",
  },
  {
    to: "/atividades",
    title: "Segurança e atividades",
    description:
      "Acompanhe acessos, alterações e ações realizadas dentro da empresa.",
    icon: "clock",
    cargos: ["ADMIN", "GERENTE"],
  },
  {
    to: "/plano-consumo",
    title: "Assinatura e plano",
    description:
      "Consulte o plano atual, limites disponíveis e consumo dos recursos.",
    icon: "lock",
    cargos: ["ADMIN"],
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
            ? "Gerencie seus dados de conta e segurança. As notificações ficam disponíveis pelo sino no topo."
            : "As configurações menos frequentes ficam organizadas em um único lugar. As notificações são acessadas pelo sino no topo."
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

      <div className="settings-hub-grid">
        {cardsDisponiveis.map((card) => (
          <Link className="settings-hub-card" to={card.to} key={card.to}>
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
              →
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
