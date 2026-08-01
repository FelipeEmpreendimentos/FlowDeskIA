import type { CargoUsuario } from "./index";

export type TipoCanalChatInterno = "GERAL" | "DIRETO" | "GRUPO";

export interface ChatInternoAutor {
  id: number;
  nome: string;
  cargo: CargoUsuario;
  foto_perfil: string | null;
  ativo: boolean;
}

export type ChatInternoUsuario = ChatInternoAutor;

export interface ChatInternoMensagem {
  id: number;
  canal_id: number;
  conteudo: string;
  created_at: string;
  autor: ChatInternoAutor;
}

export interface ChatInternoCanal {
  id: number;
  tipo: TipoCanalChatInterno;
  nome: string;
  created_at: string;
  membros: ChatInternoAutor[];
  ultima_mensagem: ChatInternoMensagem | null;
  nao_lidas: number;
}

export interface ChatInternoResumo {
  nao_lidas: number;
  ultima_mensagem_id: number | null;
}

export interface ChatInternoLeitura {
  canal_id: number;
  ultima_mensagem_id: number;
  updated_at: string;
}
