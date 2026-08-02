export type StatusPlataforma =
  | "TRIAL"
  | "ATIVA"
  | "SUSPENSA"
  | "CANCELADA"
  | "ARQUIVADA";

export interface SuperAdminUsuario {
  id: number;
  nome: string;
  email: string;
  ativo: boolean;
  dois_fatores_ativo: boolean;
  ultimo_login: string | null;
  created_at: string;
}

export interface SuperAdminDashboard {
  empresas_total: number;
  empresas_ativas: number;
  empresas_trial: number;
  empresas_suspensas: number;
  usuarios_ativos: number;
  agendamentos_mes: number;
  conversas_mes: number;
  planos_ativos: number;
  empresas_por_plano: Array<{ plano: string; empresas: number }>;
  alertas: Array<{ tipo: string; titulo: string; mensagem: string }>;
}

export interface SuperAdminFinancialDashboard {
  start_date: string;
  end_date: string;
  companies_total: number;
  companies_active: number;
  companies_trial: number;
  companies_suspended: number;
  companies_overdue: number;
  new_companies_period: number;
  active_users: number;
  appointments_period: number;
  conversations_period: number;
  active_plans: number;
  active_ai_addons: number;
  estimated_mrr: string | number;
  estimated_arr: string | number;
  new_contracts_period: number;
  new_contracts_monthly_value: string | number;
  audit_events_period: number;
  companies_by_plan: Array<{ plano: string; empresas: number }>;
  alerts: Array<{ type: string; title: string; message: string }>;
  recent_audit: Array<{
    id: number;
    action: string;
    entity: string | null;
    company_id: number | null;
    created_at: string;
  }>;
}

export interface PlanoSuperAdmin {
  id: number;
  codigo: string;
  nome: string;
  descricao: string | null;
  preco: string | number;
  preco_anual: string | number | null;
  ativo: boolean;
  periodo_teste_dias: number;
  limite_usuarios: number | null;
  limite_clientes: number | null;
  limite_agendamentos_mes: number | null;
  limite_conversas_mes: number | null;
  limite_mensagens_ia_mes: number | null;
  limite_canais: number | null;
  limite_armazenamento_mb: number | null;
  ia_incluida: boolean;
  ia_adicional_disponivel: boolean;
  recursos: Record<string, boolean>;
  created_at: string;
  updated_at: string;
}

export interface EmpresaSuperAdminResumo {
  id: number;
  nome: string;
  cnpj: string;
  email: string | null;
  cidade: string | null;
  estado: string | null;
  ativo: boolean;
  status: StatusPlataforma;
  plano_id: number | null;
  plano_nome: string | null;
  trial_fim: string | null;
  usuarios_ativos: number;
  clientes: number;
  agendamentos_mes: number;
  conversas_mes: number;
  ia_adicional_ativo: boolean;
  created_at: string;
}

export interface UsoEmpresaSuperAdmin {
  usuarios_ativos: number;
  clientes: number;
  agendamentos_mes: number;
  conversas_mes: number;
  canais_ativos: number;
  mensagens_ia_mes: number;
  limites: Record<string, number | null>;
  recursos: Record<string, boolean>;
}

export interface EmpresaSuperAdminDetalhe {
  id: number;
  nome: string;
  cnpj: string;
  telefone: string | null;
  email: string | null;
  cidade: string | null;
  estado: string | null;
  timezone: string;
  ativo: boolean;
  status: StatusPlataforma;
  plano_id: number | null;
  plano_nome: string | null;
  trial_fim: string | null;
  recursos_personalizados: Record<string, boolean>;
  limites_personalizados: Record<string, number | null>;
  ia_adicional_ativo: boolean;
  ia_limite_adicional: number;
  observacoes: string | null;
  uso: UsoEmpresaSuperAdmin;
  created_at: string;
  updated_at: string;
}

export interface ConfigIASuperAdmin {
  id: number;
  empresa_id: number;
  nome_assistente: string;
  mensagem_boas_vindas: string | null;
  prompt: string | null;
  temperatura: string | number;
}

export interface SuperAdminLog {
  id: number;
  super_admin_id: number | null;
  empresa_id: number | null;
  acao: string;
  entidade: string | null;
  entidade_id: number | null;
  dados_anteriores: Record<string, unknown> | null;
  dados_novos: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
}

export interface SuperAdminOutletContext {
  usuario: SuperAdminUsuario;
  atualizarUsuario: () => Promise<void>;
}
