import type { CargoUsuario } from "./index";

export interface ChatInternoAutor {
  id: number;
  nome: string;
  cargo: CargoUsuario;
  foto_perfil: string | null;
}

export interface ChatInternoMensagem {
  id: number;
  conteudo: string;
  created_at: string;
  autor: ChatInternoAutor;
}

export interface ChatInternoResumo {
  nao_lidas: number;
  ultima_mensagem_id: number | null;
}

export interface ChatInternoLeitura {
  ultima_mensagem_id: number;
  updated_at: string;
}
