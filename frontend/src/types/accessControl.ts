import type { CargoUsuario } from "./index";

export type ModuleCode =
  | "AGENDA"
  | "CHAT_INTERNO"
  | "CONVERSAS"
  | "CLIENTES"
  | "VEICULOS"
  | "SERVICOS"
  | "FINANCEIRO"
  | "RELATORIOS"
  | "EQUIPE";

export interface CurrentAccess {
  modules: Record<ModuleCode, boolean>;
}

export interface CompanyModule {
  code: ModuleCode;
  name: string;
  description: string;
  enabled: boolean;
}

export interface UserModulePermissions {
  user_id: number;
  name: string;
  email: string;
  role: CargoUsuario;
  active: boolean;
  permissions: Record<ModuleCode, boolean>;
  overrides: Partial<Record<ModuleCode, boolean>>;
}

export interface AccessConfiguration {
  modules: CompanyModule[];
  users: UserModulePermissions[];
}
