export type CargoUsuario = "ADMIN" | "GERENTE" | "FUNCIONARIO";
export type StatusCliente = "ATIVO" | "INATIVO" | "BLOQUEADO";
export type StatusAgendamento =
  | "PENDENTE"
  | "CONFIRMADO"
  | "EM_ANDAMENTO"
  | "FINALIZADO"
  | "CANCELADO";
export type OrigemAgendamento = "IA" | "FUNCIONARIO" | "SITE" | "WHATSAPP";
export type FormaPagamento =
  | "DINHEIRO"
  | "PIX"
  | "CARTAO_DEBITO"
  | "CARTAO_CREDITO"
  | "BOLETO";
export type StatusConversa = "ABERTA" | "EM_ATENDIMENTO" | "FINALIZADA";
export type OrigemConversa = "WHATSAPP" | "SITE" | "INSTAGRAM";
export type RemetenteMensagem = "CLIENTE" | "IA" | "FUNCIONARIO" | "GERENTE";

export type TipoVeiculo = "HATCH" | "SEDAN" | "SUV" | "CAMINHONETE" | "OUTRO";

export interface UsuarioLogado {
  id: number;
  empresa_id: number;
  nome: string;
  email: string;
  cargo: CargoUsuario;
  ativo: boolean;
}

export interface Usuario extends UsuarioLogado {
  telefone: string | null;
  foto_perfil: string | null;
  ultimo_login: string | null;
  created_at: string;
}

export interface Cliente {
  id: number;
  empresa_id: number;
  nome: string;
  telefone: string | null;
  whatsapp: string | null;
  email: string | null;
  cpf: string | null;
  data_nascimento: string | null;
  status: StatusCliente;
  ultima_visita: string | null;
  observacoes: string | null;
  created_at: string;
}

export interface Veiculo {
  id: number;
  cliente_id: number;
  tipo_veiculo: TipoVeiculo | null;
  marca: string | null;
  modelo: string | null;
  ano: number | null;
  placa: string | null;
  cor: string | null;
  apelido: string | null;
  quilometragem: number | null;
  observacoes: string | null;
  created_at: string;
}

export interface ServicoAdicional {
  tipo_veiculo: TipoVeiculo;
  valor_adicional: string | number;
}

export interface Servico {
  id: number;
  empresa_id: number;
  nome: string;
  descricao: string | null;
  duracao_minutos: number;
  preco: string | number;
  cor_agenda: string | null;
  ativo: boolean;
  adicional_por_tipo_ativo: boolean;
  adicionais: ServicoAdicional[];
}

export interface Agendamento {
  id: number;
  empresa_id: number;
  cliente_id: number;
  veiculo_id: number | null;
  servico_id: number;
  funcionario_id: number | null;
  data: string;
  hora_inicio: string;
  hora_fim: string;
  status: StatusAgendamento;
  origem: OrigemAgendamento;
  valor_base: string | number;
  valor_adicional: string | number;
  valor_final: string | number | null;
  tipo_veiculo_cobrado: TipoVeiculo | null;
  forma_pagamento: FormaPagamento | null;
  confirmado_em: string | null;
  cancelado_em: string | null;
  finalizado_em: string | null;
  observacoes: string | null;
  created_at: string;
}

export interface SlotDisponivel {
  hora_inicio: string;
  hora_fim: string;
  funcionario_id: number;
  funcionario_nome: string;
}

export interface Horario {
  id: number;
  empresa_id: number;
  funcionario_id: number;
  dia_semana: number;
  hora_inicio: string;
  hora_fim: string;
  pausa_inicio: string | null;
  pausa_fim: string | null;
  ativo: boolean;
}

export interface BloqueioAgenda {
  id: number;
  empresa_id: number;
  funcionario_id: number | null;
  data_inicio: string;
  data_fim: string;
  hora_inicio: string | null;
  hora_fim: string | null;
  motivo: string | null;
  created_at: string;
}

export interface Conversa {
  id: number;
  empresa_id: number;
  cliente_id: number;
  responsavel_id: number | null;
  status: StatusConversa;
  origem: OrigemConversa;
  ia_ativa: boolean;
  ultima_mensagem_id: number | null;
  ultima_interacao: string | null;
  finalizada_em: string | null;
  finalizada_por_id: number | null;
  resumo_finalizacao: string | null;
  avaliacao_solicitada: boolean;
  avaliacao_enviada_em: string | null;
  avaliacao_nota: number | null;
  avaliacao_comentario: string | null;
  avaliacao_respondida_em: string | null;
  created_at: string;
}

export interface Mensagem {
  id: number;
  conversa_id: number;
  remetente: RemetenteMensagem;
  conteudo: string;
  tipo: "TEXTO" | "IMAGEM" | "AUDIO" | "DOCUMENTO";
  arquivo_url: string | null;
  id_whatsapp: string | null;
  lida: boolean;
  data_envio: string;
}

export interface Empresa {
  id: number;
  nome: string;
  cnpj: string;
  telefone: string | null;
  email: string | null;
  plano_id: number | null;
  logo: string | null;
  cidade: string | null;
  estado: string | null;
  timezone: string;
  ativo: boolean;
  horario_abertura: string | null;
  horario_fechamento: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConfigIA {
  id: number;
  empresa_id: number;
  nome_assistente: string;
  mensagem_boas_vindas: string | null;
  prompt: string | null;
  temperatura: string | number;
}

export interface Notificacao {
  id: number;
  empresa_id: number;
  usuario_id: number | null;
  titulo: string;
  mensagem: string;
  lida: boolean;
  created_at: string;
}

export interface Integracao {
  id: number;
  empresa_id: number;
  tipo: "WHATSAPP" | "INSTAGRAM" | "FACEBOOK" | "SITE";
  nome: string | null;
  ativo: boolean;
  identificador: string | null;
  configuracoes: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardResumo {
  agendamentos_hoje: number;
  agendamentos_pendentes: number;
  conversas_abertas: number;
  clientes_ativos: number;
  notificacoes_nao_lidas: number;
}

export interface AppOutletContext {
  usuario: UsuarioLogado;
  modulos: Partial<Record<string, boolean>>;
  atualizarUsuario: () => Promise<void>;
}
