import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useOutletContext } from "react-router";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import {
  Alert,
  EmptyState,
  LoadingState,
  PageHeader,
  StatusBadge,
} from "../components/UI";
import { apiRequest } from "../services/api";
import type {
  AppOutletContext,
  BloqueioAgenda,
  CargoUsuario,
  Horario,
  Usuario,
} from "../types";
import {
  diasSemana,
  formatDate,
  formatTime,
  normalizeNullable,
  todayISO,
} from "../utils/format";

type AbaEquipe = "usuarios" | "jornadas" | "bloqueios";
type CampoBuscaUsuario = "todos" | "nome" | "email" | "telefone" | "cargo";
type FiltroStatusUsuario = "ATIVOS" | "INATIVOS" | "TODOS";
type TipoBloqueio = "DIA_INTEIRO" | "HORARIO";
type VisualizacaoBloqueio = "ATIVOS" | "HISTORICO";

interface UsuarioForm {
  nome: string;
  email: string;
  senha: string;
  confirmar_senha: string;
  telefone: string;
  cargo: CargoUsuario;
  ativo: boolean;
}

interface HorarioForm {
  funcionario_id: string;
  dia_semana: string;
  hora_inicio: string;
  hora_fim: string;
  pausa_ativa: boolean;
  pausa_inicio: string;
  pausa_fim: string;
  ativo: boolean;
}

interface PeriodoJornadaForm {
  ativo: boolean;
  hora_inicio: string;
  hora_fim: string;
  pausa_ativa: boolean;
  pausa_inicio: string;
  pausa_fim: string;
}

interface SemanaJornadaForm {
  funcionario_id: string;
  dias: Record<number, PeriodoJornadaForm>;
}

interface BloqueioForm {
  funcionario_id: string;
  tipo: TipoBloqueio;
  data_inicio: string;
  data_fim: string;
  hora_inicio: string;
  hora_fim: string;
  motivo: string;
}

const usuarioVazio: UsuarioForm = {
  nome: "",
  email: "",
  senha: "",
  confirmar_senha: "",
  telefone: "",
  cargo: "FUNCIONARIO",
  ativo: true,
};

const horarioVazio: HorarioForm = {
  funcionario_id: "",
  dia_semana: "1",
  hora_inicio: "08:00",
  hora_fim: "18:00",
  pausa_ativa: true,
  pausa_inicio: "12:00",
  pausa_fim: "13:00",
  ativo: true,
};

const ordemDiasJornada = [1, 2, 3, 4, 5, 6, 0];
const diasUteis = [1, 2, 3, 4, 5];

function criarPeriodoJornada(ativo = false): PeriodoJornadaForm {
  return {
    ativo,
    hora_inicio: "08:00",
    hora_fim: "18:00",
    pausa_ativa: ativo,
    pausa_inicio: "12:00",
    pausa_fim: "13:00",
  };
}

function criarSemanaJornada(funcionarioId = ""): SemanaJornadaForm {
  return {
    funcionario_id: funcionarioId,
    dias: {
      0: criarPeriodoJornada(false),
      1: criarPeriodoJornada(true),
      2: criarPeriodoJornada(true),
      3: criarPeriodoJornada(true),
      4: criarPeriodoJornada(true),
      5: criarPeriodoJornada(true),
      6: criarPeriodoJornada(false),
    },
  };
}

function periodosIguais(
  primeiro: PeriodoJornadaForm,
  segundo: PeriodoJornadaForm,
): boolean {
  return (
    primeiro.ativo === segundo.ativo &&
    primeiro.hora_inicio === segundo.hora_inicio &&
    primeiro.hora_fim === segundo.hora_fim &&
    primeiro.pausa_ativa === segundo.pausa_ativa &&
    primeiro.pausa_inicio === segundo.pausa_inicio &&
    primeiro.pausa_fim === segundo.pausa_fim
  );
}

const bloqueioVazio: BloqueioForm = {
  funcionario_id: "",
  tipo: "HORARIO",
  data_inicio: todayISO(),
  data_fim: todayISO(),
  hora_inicio: "08:00",
  hora_fim: "09:00",
  motivo: "",
};

const campoBuscaLabels: Record<CampoBuscaUsuario, string> = {
  todos: "Todos os campos",
  nome: "Nome",
  email: "E-mail",
  telefone: "Telefone",
  cargo: "Cargo",
};

const placeholdersBusca: Record<CampoBuscaUsuario, string> = {
  todos: "Buscar por nome, e-mail, telefone ou cargo",
  nome: "Buscar por nome",
  email: "Buscar por e-mail",
  telefone: "Buscar por telefone",
  cargo: "Buscar por cargo",
};

function normalizar(texto: string | null | undefined): string {
  return (texto ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function cargoParaBusca(cargo: CargoUsuario): string {
  if (cargo === "ADMIN") return "administrador admin";
  if (cargo === "GERENTE") return "gerente";
  return "funcionario funcionário";
}

function fimDoBloqueio(item: BloqueioAgenda): number {
  const dataFinal = item.data_fim || item.data_inicio;

  if (item.hora_fim) {
    const horario = item.hora_fim.slice(0, 8);
    return new Date(`${dataFinal}T${horario}`).getTime();
  }

  return new Date(`${dataFinal}T23:59:59.999`).getTime();
}

function bloqueioJaTerminou(
  item: BloqueioAgenda,
  referencia: number,
): boolean {
  return fimDoBloqueio(item) < referencia;
}

export function Equipe() {
  const { usuario: usuarioAtual } = useOutletContext<AppOutletContext>();
  const [aba, setAba] = useState<AbaEquipe>("usuarios");
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [horarios, setHorarios] = useState<Horario[]>([]);
  const [bloqueios, setBloqueios] = useState<BloqueioAgenda[]>([]);
  const [carregando, setCarregando] = useState(true);

  const [buscaUsuario, setBuscaUsuario] = useState("");
  const [campoBuscaUsuario, setCampoBuscaUsuario] =
    useState<CampoBuscaUsuario>("todos");
  const [filtroStatusUsuario, setFiltroStatusUsuario] =
    useState<FiltroStatusUsuario>("ATIVOS");

  const [modalUsuario, setModalUsuario] = useState(false);
  const [modalHorario, setModalHorario] = useState(false);
  const [modalSemana, setModalSemana] = useState(false);
  const [modalBloqueio, setModalBloqueio] = useState(false);
  const [editandoUsuario, setEditandoUsuario] = useState<Usuario | null>(null);
  const [editandoHorario, setEditandoHorario] = useState<Horario | null>(null);
  const [usuarioSituacao, setUsuarioSituacao] = useState<Usuario | null>(null);
  const [usuarioExclusao, setUsuarioExclusao] = useState<Usuario | null>(null);
  const [excluindoUsuario, setExcluindoUsuario] = useState(false);
  const [erroExclusaoUsuario, setErroExclusaoUsuario] = useState("");

  const [usuarioForm, setUsuarioForm] = useState<UsuarioForm>(usuarioVazio);
  const [horarioForm, setHorarioForm] = useState<HorarioForm>(horarioVazio);
  const [semanaForm, setSemanaForm] = useState<SemanaJornadaForm>(
    criarSemanaJornada(),
  );
  const [semanaPersonalizada, setSemanaPersonalizada] = useState(false);
  const [jornadasAbertas, setJornadasAbertas] = useState<Set<number>>(
    new Set(),
  );
  const [bloqueioForm, setBloqueioForm] =
    useState<BloqueioForm>(bloqueioVazio);
  const [visualizacaoBloqueio, setVisualizacaoBloqueio] =
    useState<VisualizacaoBloqueio>("ATIVOS");
  const [bloqueioExclusao, setBloqueioExclusao] =
    useState<BloqueioAgenda | null>(null);
  const [excluindoBloqueio, setExcluindoBloqueio] = useState(false);
  const [agoraBloqueios, setAgoraBloqueios] = useState(() => Date.now());

  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [mostrarConfirmacaoSenha, setMostrarConfirmacaoSenha] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [alterandoSituacao, setAlterandoSituacao] = useState(false);

  const podeGerenciar = ["ADMIN", "GERENTE"].includes(usuarioAtual.cargo);

  function podeAdministrarUsuario(item: Usuario): boolean {
    if (!podeGerenciar || item.id === usuarioAtual.id) return false;
    return usuarioAtual.cargo === "ADMIN" || item.cargo === "FUNCIONARIO";
  }

  async function carregar() {
    setCarregando(true);
    setErro("");
    try {
      const [dadosUsuarios, dadosHorarios, dadosBloqueios] = await Promise.all([
        apiRequest<Usuario[]>("/usuarios?limit=100"),
        apiRequest<Horario[]>("/horarios"),
        apiRequest<BloqueioAgenda[]>("/bloqueios-agenda"),
      ]);
      setUsuarios(dadosUsuarios);
      setHorarios(dadosHorarios);
      setBloqueios(dadosBloqueios);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar a equipe.",
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
  }, []);

  useEffect(() => {
    if (!sucesso) return;
    const timer = window.setTimeout(() => setSucesso(""), 4000);
    return () => window.clearTimeout(timer);
  }, [sucesso]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setAgoraBloqueios(Date.now());
    }, 60000);

    return () => window.clearInterval(timer);
  }, []);

  const usuariosAtivos = useMemo(
    () => usuarios.filter((item) => item.ativo),
    [usuarios],
  );

  const nomeUsuario = (id: number | null) =>
    id
      ? usuarios.find((item) => item.id === id)?.nome ?? `Usuário #${id}`
      : "Toda a empresa";

  const usuariosFiltrados = useMemo(() => {
    const termo = normalizar(buscaUsuario);

    return usuarios.filter((item) => {
      const statusConfere =
        filtroStatusUsuario === "TODOS" ||
        (filtroStatusUsuario === "ATIVOS" && item.ativo) ||
        (filtroStatusUsuario === "INATIVOS" && !item.ativo);

      if (!statusConfere) return false;
      if (!termo) return true;

      const campos: Record<CampoBuscaUsuario, string> = {
        todos: [
          item.nome,
          item.email,
          item.telefone,
          cargoParaBusca(item.cargo),
        ]
          .map(normalizar)
          .join(" "),
        nome: normalizar(item.nome),
        email: normalizar(item.email),
        telefone: normalizar(item.telefone),
        cargo: normalizar(cargoParaBusca(item.cargo)),
      };

      return campos[campoBuscaUsuario].includes(termo);
    });
  }, [buscaUsuario, campoBuscaUsuario, filtroStatusUsuario, usuarios]);

  const bloqueiosAtivos = useMemo(
    () =>
      bloqueios
        .filter((item) => !bloqueioJaTerminou(item, agoraBloqueios))
        .sort((a, b) => fimDoBloqueio(a) - fimDoBloqueio(b)),
    [agoraBloqueios, bloqueios],
  );

  const bloqueiosHistorico = useMemo(
    () =>
      bloqueios
        .filter((item) => bloqueioJaTerminou(item, agoraBloqueios))
        .sort((a, b) => fimDoBloqueio(b) - fimDoBloqueio(a)),
    [agoraBloqueios, bloqueios],
  );

  const bloqueiosExibidos =
    visualizacaoBloqueio === "ATIVOS"
      ? bloqueiosAtivos
      : bloqueiosHistorico;

  const jornadasPorFuncionario = useMemo(() => {
    const ids = new Set<number>();

    horarios.forEach((item) => ids.add(item.funcionario_id));
    usuarios
      .filter((item) => item.ativo && item.cargo === "FUNCIONARIO")
      .forEach((item) => ids.add(item.id));

    return Array.from(ids)
      .map((funcionarioId) => ({
        funcionario_id: funcionarioId,
        nome: nomeUsuario(funcionarioId),
        usuario: usuarios.find((item) => item.id === funcionarioId) ?? null,
        horarios: horarios
          .filter((item) => item.funcionario_id === funcionarioId)
          .sort((a, b) => a.dia_semana - b.dia_semana),
      }))
      .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  }, [horarios, usuarios]);

  function abrirNovoUsuario() {
    setEditandoUsuario(null);
    setUsuarioForm({ ...usuarioVazio });
    setMostrarSenha(false);
    setMostrarConfirmacaoSenha(false);
    setErro("");
    setModalUsuario(true);
  }

  function abrirEditarUsuario(item: Usuario) {
    setEditandoUsuario(item);
    setUsuarioForm({
      nome: item.nome,
      email: item.email,
      senha: "",
      confirmar_senha: "",
      telefone: item.telefone ?? "",
      cargo: item.cargo,
      ativo: item.ativo,
    });
    setErro("");
    setModalUsuario(true);
  }

  async function salvarUsuario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro("");

    if (!editandoUsuario && usuarioForm.senha !== usuarioForm.confirmar_senha) {
      setErro("As senhas informadas não são iguais.");
      return;
    }

    setSalvando(true);
    try {
      if (editandoUsuario) {
        await apiRequest<Usuario>(`/usuarios/${editandoUsuario.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            nome: usuarioForm.nome.trim(),
            email: usuarioForm.email.trim(),
            telefone: normalizeNullable(usuarioForm.telefone),
            cargo: usuarioForm.cargo,
            ativo: usuarioForm.ativo,
          }),
        });
        setSucesso("Usuário atualizado com sucesso.");
      } else {
        await apiRequest<Usuario>("/usuarios", {
          method: "POST",
          body: JSON.stringify({
            nome: usuarioForm.nome.trim(),
            email: usuarioForm.email.trim(),
            senha: usuarioForm.senha,
            telefone: normalizeNullable(usuarioForm.telefone),
            foto_perfil: null,
            cargo: usuarioForm.cargo,
          }),
        });
        setSucesso("Usuário cadastrado com sucesso.");
      }
      setModalUsuario(false);
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar o usuário.",
      );
    } finally {
      setSalvando(false);
    }
  }

  async function confirmarSituacaoUsuario() {
    if (!usuarioSituacao) return;
    setAlterandoSituacao(true);
    setErro("");
    try {
      if (usuarioSituacao.ativo) {
        await apiRequest<void>(`/usuarios/${usuarioSituacao.id}`, {
          method: "DELETE",
        });
        setSucesso("Usuário desativado com sucesso.");
      } else {
        await apiRequest<Usuario>(`/usuarios/${usuarioSituacao.id}`, {
          method: "PATCH",
          body: JSON.stringify({ ativo: true }),
        });
        setSucesso("Usuário reativado com sucesso.");
      }
      setUsuarioSituacao(null);
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível alterar a situação do usuário.",
      );
    } finally {
      setAlterandoSituacao(false);
    }
  }

  function abrirExclusaoUsuario(item: Usuario) {
    setUsuarioExclusao(item);
    setErroExclusaoUsuario("");
  }

  function fecharExclusaoUsuario() {
    if (excluindoUsuario) return;
    setUsuarioExclusao(null);
    setErroExclusaoUsuario("");
  }

  async function confirmarExclusaoUsuario() {
    if (!usuarioExclusao) return;

    setExcluindoUsuario(true);
    setErroExclusaoUsuario("");
    try {
      await apiRequest<void>(`/usuarios/${usuarioExclusao.id}/permanente`, {
        method: "DELETE",
      });
      setUsuarioExclusao(null);
      setSucesso("Usuário excluído com sucesso.");
      await carregar();
    } catch (error) {
      setErroExclusaoUsuario(
        error instanceof Error
          ? error.message
          : "Não foi possível excluir o usuário.",
      );
    } finally {
      setExcluindoUsuario(false);
    }
  }

  function montarSemanaFuncionario(funcionarioId: number): SemanaJornadaForm {
    const dias = criarSemanaJornada(funcionarioId.toString()).dias;

    for (const dia of ordemDiasJornada) {
      const registro = horarios.find(
        (item) =>
          item.funcionario_id === funcionarioId && item.dia_semana === dia,
      );

      if (!registro) {
        dias[dia] = criarPeriodoJornada(false);
        continue;
      }

      dias[dia] = {
        ativo: registro.ativo,
        hora_inicio: formatTime(registro.hora_inicio),
        hora_fim: formatTime(registro.hora_fim),
        pausa_ativa: Boolean(registro.pausa_inicio && registro.pausa_fim),
        pausa_inicio: registro.pausa_inicio
          ? formatTime(registro.pausa_inicio)
          : "12:00",
        pausa_fim: registro.pausa_fim
          ? formatTime(registro.pausa_fim)
          : "13:00",
      };
    }

    return {
      funcionario_id: funcionarioId.toString(),
      dias,
    };
  }

  function abrirConfigurarSemana(funcionarioId?: number) {
    const id = funcionarioId ?? 0;
    const novaSemana = id
      ? montarSemanaFuncionario(id)
      : criarSemanaJornada();
    const base = novaSemana.dias[1];
    const diasIguais = diasUteis.every((dia) =>
      periodosIguais(base, novaSemana.dias[dia]),
    );

    setSemanaForm(novaSemana);
    setSemanaPersonalizada(!diasIguais);
    setErro("");
    setModalSemana(true);
  }

  function selecionarFuncionarioSemana(funcionarioId: string) {
    if (!funcionarioId) {
      setSemanaForm(criarSemanaJornada());
      setSemanaPersonalizada(false);
      return;
    }

    const novaSemana = montarSemanaFuncionario(Number(funcionarioId));
    const base = novaSemana.dias[1];
    setSemanaForm(novaSemana);
    setSemanaPersonalizada(
      !diasUteis.every((dia) => periodosIguais(base, novaSemana.dias[dia])),
    );
  }

  function atualizarDiaSemana(
    dia: number,
    alteracoes: Partial<PeriodoJornadaForm>,
  ) {
    setSemanaForm((atual) => ({
      ...atual,
      dias: {
        ...atual.dias,
        [dia]: {
          ...atual.dias[dia],
          ...alteracoes,
        },
      },
    }));
  }

  function atualizarDiasUteis(
    alteracoes: Partial<PeriodoJornadaForm>,
  ) {
    setSemanaForm((atual) => {
      const dias = { ...atual.dias };
      diasUteis.forEach((dia) => {
        dias[dia] = { ...dias[dia], ...alteracoes };
      });
      return { ...atual, dias };
    });
  }

  function alternarPersonalizacaoSemana(personalizar: boolean) {
    setSemanaPersonalizada(personalizar);

    if (!personalizar) {
      const base = semanaForm.dias[1];
      atualizarDiasUteis({ ...base });
    }
  }

  async function salvarSemana(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro("");

    if (!semanaForm.funcionario_id) {
      setErro("Selecione o funcionário para configurar a jornada.");
      return;
    }

    setSalvando(true);
    const funcionarioId = Number(semanaForm.funcionario_id);

    try {
      for (const dia of ordemDiasJornada) {
        const configuracao = semanaForm.dias[dia];
        const existentes = horarios.filter(
          (item) =>
            item.funcionario_id === funcionarioId &&
            item.dia_semana === dia,
        );

        if (!configuracao.ativo) {
          for (const item of existentes) {
            await apiRequest<void>(`/horarios/${item.id}`, {
              method: "DELETE",
            });
          }
          continue;
        }

        const payload = {
          dia_semana: dia,
          hora_inicio: `${configuracao.hora_inicio}:00`,
          hora_fim: `${configuracao.hora_fim}:00`,
          pausa_inicio: configuracao.pausa_ativa
            ? `${configuracao.pausa_inicio}:00`
            : null,
          pausa_fim: configuracao.pausa_ativa
            ? `${configuracao.pausa_fim}:00`
            : null,
          ativo: true,
        };

        if (existentes.length > 0) {
          await apiRequest<Horario>(`/horarios/${existentes[0].id}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          });

          for (const duplicado of existentes.slice(1)) {
            await apiRequest<void>(`/horarios/${duplicado.id}`, {
              method: "DELETE",
            });
          }
        } else {
          await apiRequest<Horario>("/horarios", {
            method: "POST",
            body: JSON.stringify({
              funcionario_id: funcionarioId,
              ...payload,
            }),
          });
        }
      }

      setModalSemana(false);
      setSucesso("Jornada semanal salva com sucesso.");
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar a jornada semanal.",
      );
    } finally {
      setSalvando(false);
    }
  }

  function alternarDetalhesJornada(funcionarioId: number) {
    setJornadasAbertas((atual) => {
      const proximo = new Set(atual);
      if (proximo.has(funcionarioId)) proximo.delete(funcionarioId);
      else proximo.add(funcionarioId);
      return proximo;
    });
  }

  function abrirNovoHorarioIndividual(funcionarioId: number, diaSemana: number) {
    setEditandoHorario(null);
    setHorarioForm({
      ...horarioVazio,
      funcionario_id: funcionarioId.toString(),
      dia_semana: diaSemana.toString(),
      pausa_ativa: diaSemana >= 1 && diaSemana <= 5,
    });
    setErro("");
    setModalHorario(true);
  }

  function abrirNovoHorario() {
    abrirConfigurarSemana();
  }

  function abrirEditarHorario(item: Horario) {
    const temPausa = Boolean(item.pausa_inicio && item.pausa_fim);
    setEditandoHorario(item);
    setHorarioForm({
      funcionario_id: item.funcionario_id.toString(),
      dia_semana: item.dia_semana.toString(),
      hora_inicio: formatTime(item.hora_inicio),
      hora_fim: formatTime(item.hora_fim),
      pausa_ativa: temPausa,
      pausa_inicio: item.pausa_inicio ? formatTime(item.pausa_inicio) : "12:00",
      pausa_fim: item.pausa_fim ? formatTime(item.pausa_fim) : "13:00",
      ativo: item.ativo,
    });
    setErro("");
    setModalHorario(true);
  }

  async function salvarHorario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");

    const payload = {
      dia_semana: Number(horarioForm.dia_semana),
      hora_inicio: `${horarioForm.hora_inicio}:00`,
      hora_fim: `${horarioForm.hora_fim}:00`,
      pausa_inicio: horarioForm.pausa_ativa
        ? `${horarioForm.pausa_inicio}:00`
        : null,
      pausa_fim: horarioForm.pausa_ativa
        ? `${horarioForm.pausa_fim}:00`
        : null,
      ativo: horarioForm.ativo,
    };

    try {
      if (editandoHorario) {
        await apiRequest<Horario>(`/horarios/${editandoHorario.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        setSucesso("Jornada atualizada com sucesso.");
      } else {
        await apiRequest<Horario>("/horarios", {
          method: "POST",
          body: JSON.stringify({
            funcionario_id: Number(horarioForm.funcionario_id),
            ...payload,
          }),
        });
        setSucesso("Jornada cadastrada com sucesso.");
      }
      setModalHorario(false);
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar a jornada.",
      );
    } finally {
      setSalvando(false);
    }
  }

  async function excluirHorario(item: Horario) {
    if (!window.confirm("Excluir esta jornada de trabalho?")) return;
    try {
      await apiRequest<void>(`/horarios/${item.id}`, { method: "DELETE" });
      setSucesso("Jornada excluída com sucesso.");
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível excluir a jornada.",
      );
    }
  }

  function abrirNovoBloqueio() {
    setBloqueioForm({
      ...bloqueioVazio,
      funcionario_id: "",
      data_inicio: todayISO(),
      data_fim: todayISO(),
    });
    setErro("");
    setModalBloqueio(true);
  }

  async function salvarBloqueio(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");

    const bloqueioPorHorario = bloqueioForm.tipo === "HORARIO";

    try {
      await apiRequest<BloqueioAgenda>("/bloqueios-agenda", {
        method: "POST",
        body: JSON.stringify({
          funcionario_id: bloqueioForm.funcionario_id
            ? Number(bloqueioForm.funcionario_id)
            : null,
          data_inicio: bloqueioForm.data_inicio,
          data_fim: bloqueioPorHorario
            ? bloqueioForm.data_inicio
            : bloqueioForm.data_fim,
          hora_inicio: bloqueioPorHorario
            ? `${bloqueioForm.hora_inicio}:00`
            : null,
          hora_fim: bloqueioPorHorario
            ? `${bloqueioForm.hora_fim}:00`
            : null,
          motivo: normalizeNullable(bloqueioForm.motivo),
        }),
      });
      setModalBloqueio(false);
      setBloqueioForm({ ...bloqueioVazio });
      setSucesso("Bloqueio criado com sucesso.");
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível criar o bloqueio.",
      );
    } finally {
      setSalvando(false);
    }
  }

  function abrirExclusaoBloqueio(item: BloqueioAgenda) {
    setErro("");
    setBloqueioExclusao(item);
  }

  function fecharExclusaoBloqueio() {
    if (excluindoBloqueio) return;
    setBloqueioExclusao(null);
    setErro("");
  }

  async function confirmarExclusaoBloqueio() {
    if (!bloqueioExclusao) return;

    setExcluindoBloqueio(true);
    setErro("");

    try {
      await apiRequest<void>(`/bloqueios-agenda/${bloqueioExclusao.id}`, {
        method: "DELETE",
      });
      setBloqueioExclusao(null);
      setSucesso("Bloqueio excluído com sucesso.");
      await carregar();
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível excluir o bloqueio.",
      );
    } finally {
      setExcluindoBloqueio(false);
    }
  }

  const acaoPrincipal = () => {
    if (aba === "usuarios") abrirNovoUsuario();
    if (aba === "jornadas") abrirNovoHorario();
    if (aba === "bloqueios") abrirNovoBloqueio();
  };

  const labelAcao =
    aba === "usuarios"
      ? "Novo usuário"
      : aba === "jornadas"
        ? "Configurar jornada"
        : "Novo bloqueio";

  function periodoBloqueio(item: BloqueioAgenda): string {
    if (item.hora_inicio && item.hora_fim) {
      return `${formatDate(item.data_inicio)} · ${formatTime(
        item.hora_inicio,
      )} às ${formatTime(item.hora_fim)}`;
    }

    if (item.data_inicio === item.data_fim) {
      return `${formatDate(item.data_inicio)} · Dia inteiro`;
    }

    return `${formatDate(item.data_inicio)} até ${formatDate(
      item.data_fim,
    )} · Dias inteiros`;
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Administração"
        title="Equipe"
        description="Gerencie usuários, jornadas de trabalho e indisponibilidades."
        actions={
          podeGerenciar ? (
            <button
              className="button button-primary"
              type="button"
              onClick={acaoPrincipal}
            >
              <Icon name="plus" size={18} />
              {labelAcao}
            </button>
          ) : undefined
        }
      />

      {sucesso && (
        <div className="app-toast-region" aria-live="polite" aria-atomic="true">
          <div className="app-toast app-toast-success" role="status">
            <span className="app-toast-icon">
              <Icon name="check" size={18} />
            </span>
            <div className="app-toast-copy">
              <strong>Sucesso</strong>
              <span>{sucesso}</span>
            </div>
            <button
              className="app-toast-close"
              type="button"
              onClick={() => setSucesso("")}
              aria-label="Fechar notificação"
            >
              <Icon name="close" size={17} />
            </button>
          </div>
        </div>
      )}

      {erro &&
        !modalUsuario &&
        !modalHorario &&
        !modalSemana &&
        !modalBloqueio &&
        !usuarioSituacao &&
        !usuarioExclusao &&
        !bloqueioExclusao && (
        <Alert>{erro}</Alert>
      )}

      {!podeGerenciar && (
        <Alert type="info">Seu perfil possui acesso somente para consulta.</Alert>
      )}

      <div className="tabs">
        <button className={aba === "usuarios" ? "tab-active" : ""} onClick={() => setAba("usuarios")}>Usuários</button>
        <button className={aba === "jornadas" ? "tab-active" : ""} onClick={() => setAba("jornadas")}>Jornadas</button>
        <button className={aba === "bloqueios" ? "tab-active" : ""} onClick={() => setAba("bloqueios")}>Bloqueios</button>
      </div>

      <section className="content-card">
        {aba === "usuarios" && (
          <div className="toolbar team-toolbar">
            <div className="toolbar-search-group">
              <label className="search-field">
                <Icon name="search" size={18} />
                <input value={buscaUsuario} onChange={(event) => setBuscaUsuario(event.target.value)} placeholder={placeholdersBusca[campoBuscaUsuario]} />
              </label>
              <label className="search-filter">
                <Icon name="filter" size={17} />
                <select value={campoBuscaUsuario} onChange={(event) => setCampoBuscaUsuario(event.target.value as CampoBuscaUsuario)} aria-label="Campo da busca">
                  {(Object.keys(campoBuscaLabels) as CampoBuscaUsuario[]).map((campo) => <option key={campo} value={campo}>{campoBuscaLabels[campo]}</option>)}
                </select>
              </label>
            </div>
            <select className="team-status-filter" value={filtroStatusUsuario} onChange={(event) => setFiltroStatusUsuario(event.target.value as FiltroStatusUsuario)} aria-label="Status dos usuários">
              <option value="ATIVOS">Ativos</option>
              <option value="INATIVOS">Inativos</option>
              <option value="TODOS">Todos</option>
            </select>
          </div>
        )}

        {carregando ? (
          <LoadingState label="Carregando equipe..." />
        ) : aba === "usuarios" ? (
          usuariosFiltrados.length === 0 ? (
            <EmptyState icon="team" title="Nenhum usuário encontrado" description="Altere a busca ou os filtros para visualizar outros usuários." />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Usuário</th><th>Contato</th><th>Cargo</th><th>Último acesso</th><th>Status</th><th className="actions-column">Ações</th></tr></thead>
                <tbody>
                  {usuariosFiltrados.map((item) => (
                    <tr key={item.id}>
                      <td><div className="entity-cell"><span className="entity-avatar">{item.nome.charAt(0).toUpperCase()}</span><div><strong>{item.nome}</strong><small>{item.email}</small></div></div></td>
                      <td>{item.telefone ?? "—"}</td>
                      <td><StatusBadge value={item.cargo} /></td>
                      <td>{item.ultimo_login ? new Date(item.ultimo_login).toLocaleString("pt-BR") : "Nunca"}</td>
                      <td><StatusBadge value={item.ativo ? "ATIVO" : "INATIVO"} /></td>
                      <td>
                        <div className="row-actions">
                          <button className="icon-button" type="button" onClick={() => abrirEditarUsuario(item)} disabled={!podeGerenciar} title="Editar usuário"><Icon name="edit" size={17} /></button>
                          {podeAdministrarUsuario(item) && (
                            <>
                              <button className={`icon-button ${item.ativo ? "danger" : "success"}`} type="button" onClick={() => setUsuarioSituacao(item)} title={item.ativo ? "Desativar usuário" : "Reativar usuário"}>
                                <Icon name={item.ativo ? "pause" : "refresh"} size={17} />
                              </button>
                              <button className="icon-button danger" type="button" onClick={() => abrirExclusaoUsuario(item)} title="Excluir usuário permanentemente">
                                <Icon name="trash" size={17} />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : aba === "jornadas" ? (
          jornadasPorFuncionario.length === 0 ? (
            <EmptyState icon="clock" title="Nenhuma jornada cadastrada" description="Configure a jornada e o horário de almoço de cada funcionário." />
          ) : (
            <div className="employee-schedule-list">
              {jornadasPorFuncionario.map((grupo) => {
                const porDia = new Map<number, Horario>(grupo.horarios.map((item) => [item.dia_semana, item] as [number, Horario]));
                const uteis = diasUteis.map((dia) => porDia.get(dia)).filter((item): item is Horario => Boolean(item));
                const todosUteisIguais = uteis.length === 5 && uteis.every((item) => formatTime(item.hora_inicio) === formatTime(uteis[0].hora_inicio) && formatTime(item.hora_fim) === formatTime(uteis[0].hora_fim) && formatTime(item.pausa_inicio ?? "") === formatTime(uteis[0].pausa_inicio ?? "") && formatTime(item.pausa_fim ?? "") === formatTime(uteis[0].pausa_fim ?? ""));
                const sabado = porDia.get(6);
                const domingo = porDia.get(0);
                const aberto = jornadasAbertas.has(grupo.funcionario_id);
                const resumoUteis = uteis.length === 0 ? "Não configurado" : todosUteisIguais ? `${formatTime(uteis[0].hora_inicio)} — ${formatTime(uteis[0].hora_fim)}` : `${uteis.length} dias com horários personalizados`;
                const resumoIntervalo = todosUteisIguais && uteis[0].pausa_inicio && uteis[0].pausa_fim ? `${formatTime(uteis[0].pausa_inicio)} — ${formatTime(uteis[0].pausa_fim)}` : todosUteisIguais ? "Sem intervalo" : "Consultar detalhes";
                const resumoFimSemana = [sabado ? `Sáb ${formatTime(sabado.hora_inicio)}–${formatTime(sabado.hora_fim)}` : null, domingo ? `Dom ${formatTime(domingo.hora_inicio)}–${formatTime(domingo.hora_fim)}` : null].filter(Boolean).join(" · ") || "Não trabalha";
                return (
                  <article className={`employee-schedule-card ${aberto ? "employee-schedule-card-open" : ""}`} key={grupo.funcionario_id}>
                    <div className="employee-schedule-header">
                      <div className="entity-cell"><span className="entity-avatar">{grupo.nome.charAt(0).toUpperCase()}</span><div><strong>{grupo.nome}</strong><small>{grupo.usuario?.cargo === "ADMIN" ? "Administrador" : grupo.usuario?.cargo === "GERENTE" ? "Gerente" : "Funcionário"}</small></div></div>
                      <div className="employee-schedule-actions">
                        <button className="button button-secondary button-small" type="button" onClick={() => abrirConfigurarSemana(grupo.funcionario_id)} disabled={!podeGerenciar}><Icon name="edit" size={15} />Editar jornada</button>
                        <button className="schedule-expand-button" type="button" onClick={() => alternarDetalhesJornada(grupo.funcionario_id)} aria-expanded={aberto}><span>{aberto ? "Ocultar" : "Ver detalhes"}</span><strong aria-hidden="true">{aberto ? "−" : "+"}</strong></button>
                      </div>
                    </div>
                    <div className="employee-schedule-summary"><span><small>Segunda a sexta</small><strong>{resumoUteis}</strong></span><span><small>Intervalo</small><strong>{resumoIntervalo}</strong></span><span><small>Fim de semana</small><strong>{resumoFimSemana}</strong></span></div>
                    {aberto && (
                      <div className="employee-schedule-details">
                        {ordemDiasJornada.map((dia) => {
                          const item = porDia.get(dia);
                          return (
                            <div className="schedule-day-row" key={dia}>
                              <div><strong>{diasSemana[dia]}</strong><small>{item ? item.ativo ? "Jornada ativa" : "Jornada inativa" : "Não trabalha"}</small></div>
                              <span>{item ? `${formatTime(item.hora_inicio)} — ${formatTime(item.hora_fim)}` : "—"}</span>
                              <span>{item?.pausa_inicio && item?.pausa_fim ? `${formatTime(item.pausa_inicio)} — ${formatTime(item.pausa_fim)}` : item ? "Sem intervalo" : "—"}</span>
                              <div className="row-actions">
                                {item ? <><button className="icon-button" type="button" onClick={() => abrirEditarHorario(item)} disabled={!podeGerenciar} title={`Editar ${diasSemana[dia]}`}><Icon name="edit" size={16} /></button><button className="icon-button danger" type="button" onClick={() => void excluirHorario(item)} disabled={!podeGerenciar} title={`Excluir ${diasSemana[dia]}`}><Icon name="trash" size={16} /></button></> : <button className="button button-ghost button-small" type="button" onClick={() => abrirNovoHorarioIndividual(grupo.funcionario_id, dia)} disabled={!podeGerenciar}><Icon name="plus" size={14} />Adicionar</button>}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )
        ) : (
          <div className="schedule-blocks-section">
            <div className="schedule-blocks-tabs" role="tablist">
              <button className={visualizacaoBloqueio === "ATIVOS" ? "schedule-blocks-tab-active" : ""} type="button" onClick={() => setVisualizacaoBloqueio("ATIVOS")}><Icon name="calendar" size={16} />Ativos<span>{bloqueiosAtivos.length}</span></button>
              <button className={visualizacaoBloqueio === "HISTORICO" ? "schedule-blocks-tab-active" : ""} type="button" onClick={() => setVisualizacaoBloqueio("HISTORICO")}><Icon name="clock" size={16} />Histórico<span>{bloqueiosHistorico.length}</span></button>
            </div>
            {bloqueiosExibidos.length === 0 ? (
              <EmptyState icon="calendar" title={visualizacaoBloqueio === "ATIVOS" ? "Nenhum bloqueio ativo" : "Nenhum bloqueio no histórico"} description={visualizacaoBloqueio === "ATIVOS" ? "Bloqueios atuais e futuros aparecerão aqui." : "Os bloqueios encerrados serão organizados automaticamente nesta aba."} />
            ) : (
              <div className="table-wrap"><table className="data-table"><thead><tr><th>Responsável</th><th>Tipo</th><th>Período</th><th>Motivo</th><th>Status</th><th className="actions-column">Ações</th></tr></thead><tbody>{bloqueiosExibidos.map((item) => { const encerrado = bloqueioJaTerminou(item, agoraBloqueios); return <tr key={item.id}><td>{nomeUsuario(item.funcionario_id)}</td><td><span className={`status-badge ${item.hora_inicio && item.hora_fim ? "status-timed-block" : "status-full-day-block"}`}>{item.hora_inicio && item.hora_fim ? "Horário" : "Dia inteiro"}</span></td><td>{periodoBloqueio(item)}</td><td>{item.motivo ?? "Sem motivo informado"}</td><td><span className={`status-badge ${encerrado ? "status-block-ended" : "status-block-active"}`}>{encerrado ? "Encerrado" : "Ativo"}</span></td><td>{encerrado ? <span className="table-action-placeholder">—</span> : <button className="icon-button danger" type="button" onClick={() => abrirExclusaoBloqueio(item)} disabled={!podeGerenciar} title="Excluir bloqueio"><Icon name="trash" size={17} /></button>}</td></tr>; })}</tbody></table></div>
            )}
          </div>
        )}
      </section>

      <Modal open={modalUsuario} title={editandoUsuario ? "Editar usuário" : "Novo usuário"} subtitle="Defina os dados de acesso e o nível de permissão." onClose={() => setModalUsuario(false)}>
        <form onSubmit={salvarUsuario}>
          {erro && <Alert>{erro}</Alert>}
          <div className="form-grid form-grid-2">
            <label className="field field-span-2">Nome<input value={usuarioForm.nome} onChange={(event) => setUsuarioForm({ ...usuarioForm, nome: event.target.value })} required /></label>
            <label className="field">E-mail<input type="email" value={usuarioForm.email} onChange={(event) => setUsuarioForm({ ...usuarioForm, email: event.target.value })} required /></label>
            <label className="field">Telefone<input value={usuarioForm.telefone} inputMode="numeric" maxLength={15} onChange={(event) => setUsuarioForm({ ...usuarioForm, telefone: event.target.value })} /></label>
            {!editandoUsuario && <><label className="field">Senha inicial<div className="password-field"><input type={mostrarSenha ? "text" : "password"} minLength={8} value={usuarioForm.senha} onChange={(event) => setUsuarioForm({ ...usuarioForm, senha: event.target.value })} required /><button className="password-toggle" type="button" onClick={() => setMostrarSenha((valor) => !valor)} aria-label="Mostrar ou ocultar senha"><Icon name="eye" size={18} /></button></div></label><label className="field">Confirmar senha<div className="password-field"><input type={mostrarConfirmacaoSenha ? "text" : "password"} minLength={8} value={usuarioForm.confirmar_senha} onChange={(event) => setUsuarioForm({ ...usuarioForm, confirmar_senha: event.target.value })} required /><button className="password-toggle" type="button" onClick={() => setMostrarConfirmacaoSenha((valor) => !valor)} aria-label="Mostrar ou ocultar confirmação da senha"><Icon name="eye" size={18} /></button></div></label></>}
            <label className="field">Cargo<select value={usuarioForm.cargo} onChange={(event) => setUsuarioForm({ ...usuarioForm, cargo: event.target.value as CargoUsuario })}><option value="FUNCIONARIO">Funcionário</option><option value="GERENTE">Gerente</option>{usuarioAtual.cargo === "ADMIN" && <option value="ADMIN">Administrador</option>}</select></label>
            {editandoUsuario && <label className="field checkbox-field"><input type="checkbox" checked={usuarioForm.ativo} onChange={(event) => setUsuarioForm({ ...usuarioForm, ativo: event.target.checked })} />Usuário ativo</label>}
          </div>
          <div className="modal-actions"><button className="button button-secondary" type="button" onClick={() => setModalUsuario(false)}>Cancelar</button><button className="button button-primary" type="submit" disabled={salvando}>{salvando ? "Salvando..." : "Salvar usuário"}</button></div>
        </form>
      </Modal>

      <Modal open={modalSemana} title="Configurar jornada semanal" subtitle="Defina os horários de segunda a sexta e, se necessário, personalize dias específicos." onClose={() => !salvando && setModalSemana(false)} size="large">
        <form onSubmit={salvarSemana}>{erro && <Alert>{erro}</Alert>}<div className="form-grid form-grid-2"><label className="field field-span-2">Funcionário<select value={semanaForm.funcionario_id} onChange={(event) => selecionarFuncionarioSemana(event.target.value)} required><option value="">Selecione</option>{usuariosAtivos.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}</select></label><div className="schedule-mode-card field-span-2"><div><strong>Forma de configuração</strong><small>Use um horário único para os dias úteis ou personalize cada dia.</small></div><div className="schedule-mode-buttons"><button className={!semanaPersonalizada ? "schedule-mode-active" : ""} type="button" onClick={() => alternarPersonalizacaoSemana(false)}>Segunda a sexta</button><button className={semanaPersonalizada ? "schedule-mode-active" : ""} type="button" onClick={() => alternarPersonalizacaoSemana(true)}>Personalizar dias</button></div></div>{!semanaPersonalizada ? <><div className="weekday-settings field-span-2"><div className="weekday-settings-header"><div><strong>Segunda a sexta</strong><small>O mesmo horário será aplicado aos cinco dias.</small></div><label className="checkbox-field compact-checkbox"><input type="checkbox" checked={semanaForm.dias[1].ativo} onChange={(event) => atualizarDiasUteis({ ativo: event.target.checked })} />Trabalha nos dias úteis</label></div>{semanaForm.dias[1].ativo && <><div className="schedule-time-grid"><label className="field">Início da jornada<input type="time" value={semanaForm.dias[1].hora_inicio} onChange={(event) => atualizarDiasUteis({ hora_inicio: event.target.value })} required /></label><label className="field">Fim da jornada<input type="time" value={semanaForm.dias[1].hora_fim} onChange={(event) => atualizarDiasUteis({ hora_fim: event.target.value })} required /></label></div><div className="lunch-settings"><label className="lunch-toggle"><span className="switch-control"><input type="checkbox" checked={semanaForm.dias[1].pausa_ativa} onChange={(event) => atualizarDiasUteis({ pausa_ativa: event.target.checked })} /><span className="switch-slider" /></span><span><strong>Horário de almoço</strong><small>O funcionário não ficará disponível nesse período.</small></span></label>{semanaForm.dias[1].pausa_ativa && <div className="lunch-time-grid"><label className="field">Início do almoço<input type="time" value={semanaForm.dias[1].pausa_inicio} onChange={(event) => atualizarDiasUteis({ pausa_inicio: event.target.value })} required /></label><label className="field">Fim do almoço<input type="time" value={semanaForm.dias[1].pausa_fim} onChange={(event) => atualizarDiasUteis({ pausa_fim: event.target.value })} required /></label></div>}</div></>}</div>{[6,0].map((dia) => <div className="weekend-settings" key={dia}><div className="weekend-settings-header"><div><strong>{diasSemana[dia]}</strong><small>Configuração opcional.</small></div><label className="checkbox-field compact-checkbox"><input type="checkbox" checked={semanaForm.dias[dia].ativo} onChange={(event) => atualizarDiaSemana(dia, { ativo: event.target.checked })} />Trabalha</label></div>{semanaForm.dias[dia].ativo && <div className="weekend-time-grid"><label className="field">Início<input type="time" value={semanaForm.dias[dia].hora_inicio} onChange={(event) => atualizarDiaSemana(dia, { hora_inicio: event.target.value })} required /></label><label className="field">Fim<input type="time" value={semanaForm.dias[dia].hora_fim} onChange={(event) => atualizarDiaSemana(dia, { hora_fim: event.target.value })} required /></label><label className="checkbox-field compact-checkbox field-span-2"><input type="checkbox" checked={semanaForm.dias[dia].pausa_ativa} onChange={(event) => atualizarDiaSemana(dia, { pausa_ativa: event.target.checked })} />Possui intervalo</label>{semanaForm.dias[dia].pausa_ativa && <><label className="field">Início do intervalo<input type="time" value={semanaForm.dias[dia].pausa_inicio} onChange={(event) => atualizarDiaSemana(dia, { pausa_inicio: event.target.value })} required /></label><label className="field">Fim do intervalo<input type="time" value={semanaForm.dias[dia].pausa_fim} onChange={(event) => atualizarDiaSemana(dia, { pausa_fim: event.target.value })} required /></label></>}</div>}</div>)}</> : <div className="custom-days-list field-span-2">{ordemDiasJornada.map((dia) => <div className="custom-day-card" key={dia}><div className="custom-day-header"><div><strong>{diasSemana[dia]}</strong><small>{semanaForm.dias[dia].ativo ? "Jornada configurada" : "Não trabalha"}</small></div><label className="checkbox-field compact-checkbox"><input type="checkbox" checked={semanaForm.dias[dia].ativo} onChange={(event) => atualizarDiaSemana(dia, { ativo: event.target.checked })} />Trabalha</label></div>{semanaForm.dias[dia].ativo && <div className="custom-day-fields"><label className="field">Início<input type="time" value={semanaForm.dias[dia].hora_inicio} onChange={(event) => atualizarDiaSemana(dia, { hora_inicio: event.target.value })} required /></label><label className="field">Fim<input type="time" value={semanaForm.dias[dia].hora_fim} onChange={(event) => atualizarDiaSemana(dia, { hora_fim: event.target.value })} required /></label><label className="checkbox-field compact-checkbox custom-day-break-toggle"><input type="checkbox" checked={semanaForm.dias[dia].pausa_ativa} onChange={(event) => atualizarDiaSemana(dia, { pausa_ativa: event.target.checked })} />Intervalo</label>{semanaForm.dias[dia].pausa_ativa && <><label className="field">Início do intervalo<input type="time" value={semanaForm.dias[dia].pausa_inicio} onChange={(event) => atualizarDiaSemana(dia, { pausa_inicio: event.target.value })} required /></label><label className="field">Fim do intervalo<input type="time" value={semanaForm.dias[dia].pausa_fim} onChange={(event) => atualizarDiaSemana(dia, { pausa_fim: event.target.value })} required /></label></>}</div>}</div>)}</div>}</div><div className="modal-actions"><button className="button button-secondary" type="button" onClick={() => setModalSemana(false)} disabled={salvando}>Cancelar</button><button className="button button-primary" type="submit" disabled={salvando}>{salvando ? "Salvando..." : "Salvar jornada semanal"}</button></div></form>
      </Modal>

      <Modal open={modalHorario} title={editandoHorario ? "Editar jornada" : "Nova jornada"} subtitle="Configure o período de trabalho e o intervalo do funcionário." onClose={() => setModalHorario(false)}>
        <form onSubmit={salvarHorario}>{erro && <Alert>{erro}</Alert>}<div className="form-grid form-grid-2"><label className="field field-span-2">Funcionário<select value={horarioForm.funcionario_id} onChange={(event) => setHorarioForm({ ...horarioForm, funcionario_id: event.target.value })} required disabled={Boolean(editandoHorario)}><option value="">Selecione</option>{usuariosAtivos.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}</select></label><label className="field">Dia da semana<select value={horarioForm.dia_semana} onChange={(event) => setHorarioForm({ ...horarioForm, dia_semana: event.target.value })}>{diasSemana.map((dia,index) => <option key={dia} value={index}>{dia}</option>)}</select></label><label className="field checkbox-field"><input type="checkbox" checked={horarioForm.ativo} onChange={(event) => setHorarioForm({ ...horarioForm, ativo: event.target.checked })} />Jornada ativa</label><label className="field">Início da jornada<input type="time" value={horarioForm.hora_inicio} onChange={(event) => setHorarioForm({ ...horarioForm, hora_inicio: event.target.value })} required /></label><label className="field">Fim da jornada<input type="time" value={horarioForm.hora_fim} onChange={(event) => setHorarioForm({ ...horarioForm, hora_fim: event.target.value })} required /></label><div className="lunch-settings field-span-2"><label className="lunch-toggle"><span className="switch-control"><input type="checkbox" checked={horarioForm.pausa_ativa} onChange={(event) => setHorarioForm({ ...horarioForm, pausa_ativa: event.target.checked })} /><span className="switch-slider" /></span><span><strong>Horário de almoço</strong><small>O funcionário não ficará disponível durante esse intervalo.</small></span></label>{horarioForm.pausa_ativa && <div className="lunch-time-grid"><label className="field">Início do almoço<input type="time" value={horarioForm.pausa_inicio} onChange={(event) => setHorarioForm({ ...horarioForm, pausa_inicio: event.target.value })} required /></label><label className="field">Fim do almoço<input type="time" value={horarioForm.pausa_fim} onChange={(event) => setHorarioForm({ ...horarioForm, pausa_fim: event.target.value })} required /></label></div>}</div></div><div className="modal-actions"><button className="button button-secondary" type="button" onClick={() => setModalHorario(false)}>Cancelar</button><button className="button button-primary" type="submit" disabled={salvando}>{salvando ? "Salvando..." : "Salvar jornada"}</button></div></form>
      </Modal>

      <Modal open={modalBloqueio} title="Novo bloqueio" subtitle="Bloqueie um horário específico ou um período de dias." onClose={() => setModalBloqueio(false)}>
        <form onSubmit={salvarBloqueio}>{erro && <Alert>{erro}</Alert>}<div className="form-grid form-grid-2"><label className="field field-span-2">Funcionário<select value={bloqueioForm.funcionario_id} onChange={(event) => setBloqueioForm({ ...bloqueioForm, funcionario_id: event.target.value })}><option value="">Toda a empresa</option>{usuariosAtivos.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}</select></label><div className="block-type-selector field-span-2"><button className={bloqueioForm.tipo === "HORARIO" ? "block-type-active" : ""} type="button" onClick={() => setBloqueioForm({ ...bloqueioForm, tipo: "HORARIO" })}><Icon name="clock" size={18} /><span><strong>Horário específico</strong><small>Bloqueie parte de um único dia.</small></span></button><button className={bloqueioForm.tipo === "DIA_INTEIRO" ? "block-type-active" : ""} type="button" onClick={() => setBloqueioForm({ ...bloqueioForm, tipo: "DIA_INTEIRO" })}><Icon name="calendar" size={18} /><span><strong>Dia inteiro</strong><small>Bloqueie um dia ou um período de dias.</small></span></button></div>{bloqueioForm.tipo === "HORARIO" ? <><label className="field field-span-2">Data<input type="date" value={bloqueioForm.data_inicio} onChange={(event) => setBloqueioForm({ ...bloqueioForm, data_inicio: event.target.value, data_fim: event.target.value })} required /></label><label className="field">Horário inicial<input type="time" value={bloqueioForm.hora_inicio} onChange={(event) => setBloqueioForm({ ...bloqueioForm, hora_inicio: event.target.value })} required /></label><label className="field">Horário final<input type="time" value={bloqueioForm.hora_fim} onChange={(event) => setBloqueioForm({ ...bloqueioForm, hora_fim: event.target.value })} required /></label></> : <><label className="field">Data inicial<input type="date" value={bloqueioForm.data_inicio} onChange={(event) => setBloqueioForm({ ...bloqueioForm, data_inicio: event.target.value })} required /></label><label className="field">Data final<input type="date" min={bloqueioForm.data_inicio} value={bloqueioForm.data_fim} onChange={(event) => setBloqueioForm({ ...bloqueioForm, data_fim: event.target.value })} required /></label></>}<label className="field field-span-2">Motivo<input value={bloqueioForm.motivo} onChange={(event) => setBloqueioForm({ ...bloqueioForm, motivo: event.target.value })} placeholder="Folga, consulta, manutenção, reunião..." /></label></div><div className="modal-actions"><button className="button button-secondary" type="button" onClick={() => setModalBloqueio(false)}>Cancelar</button><button className="button button-primary" type="submit" disabled={salvando}>{salvando ? "Salvando..." : "Criar bloqueio"}</button></div></form>
      </Modal>

      <Modal open={Boolean(bloqueioExclusao)} title="Excluir bloqueio" subtitle="Confirme a remoção antes de continuar." onClose={fecharExclusaoBloqueio} size="small">
        {bloqueioExclusao && <div className="confirmation-dialog"><span className="confirmation-icon confirmation-icon-danger"><Icon name="trash" size={24} /></span><div className="confirmation-copy"><strong>Excluir este bloqueio da agenda?</strong><p>O bloqueio de {nomeUsuario(bloqueioExclusao.funcionario_id)}, no período {periodoBloqueio(bloqueioExclusao)}, será removido e deixará de impedir novos agendamentos. Esta ação não poderá ser desfeita.</p></div>{erro && <Alert>{erro}</Alert>}<div className="modal-actions confirmation-actions"><button className="button button-secondary" type="button" onClick={fecharExclusaoBloqueio} disabled={excluindoBloqueio}>Cancelar</button><button className="button button-danger" type="button" onClick={() => void confirmarExclusaoBloqueio()} disabled={excluindoBloqueio}>{excluindoBloqueio ? "Excluindo..." : "Excluir bloqueio"}</button></div></div>}
      </Modal>

      <Modal open={Boolean(usuarioSituacao)} title={usuarioSituacao?.ativo ? "Desativar usuário" : "Reativar usuário"} subtitle="Confirme a alteração antes de continuar." onClose={() => !alterandoSituacao && setUsuarioSituacao(null)} size="small">
        {usuarioSituacao && <div className="confirmation-dialog"><span className={`confirmation-icon ${usuarioSituacao.ativo ? "confirmation-icon-danger" : "confirmation-icon-success"}`}><Icon name={usuarioSituacao.ativo ? "pause" : "refresh"} size={24} /></span><div className="confirmation-copy"><strong>{usuarioSituacao.ativo ? `Desativar ${usuarioSituacao.nome}?` : `Reativar ${usuarioSituacao.nome}?`}</strong><p>{usuarioSituacao.ativo ? "O usuário deixará de acessar o sistema e poderá ser reativado posteriormente." : "O usuário voltará a acessar o sistema com as permissões cadastradas."}</p></div>{erro && <Alert>{erro}</Alert>}<div className="modal-actions confirmation-actions"><button className="button button-secondary" type="button" onClick={() => setUsuarioSituacao(null)} disabled={alterandoSituacao}>Cancelar</button><button className={usuarioSituacao.ativo ? "button button-danger" : "button button-primary"} type="button" onClick={() => void confirmarSituacaoUsuario()} disabled={alterandoSituacao}>{alterandoSituacao ? "Processando..." : usuarioSituacao.ativo ? "Desativar usuário" : "Reativar usuário"}</button></div></div>}
      </Modal>

      <Modal open={Boolean(usuarioExclusao)} title="Excluir usuário" subtitle="Esta ação é permanente." onClose={fecharExclusaoUsuario} size="small">
        {usuarioExclusao && <div className="confirmation-dialog"><span className="confirmation-icon confirmation-icon-danger"><Icon name="trash" size={24} /></span><div className="confirmation-copy"><strong>Excluir {usuarioExclusao.nome} permanentemente?</strong><p>Usuários sem histórico operacional podem ser removidos definitivamente. Se houver agendamentos, conversas, mensagens ou auditoria vinculados, a exclusão será bloqueada e você poderá apenas desativá-lo.</p></div>{erroExclusaoUsuario && <Alert>{erroExclusaoUsuario}</Alert>}<div className="modal-actions confirmation-actions"><button className="button button-secondary" type="button" onClick={fecharExclusaoUsuario} disabled={excluindoUsuario}>Cancelar</button><button className="button button-danger" type="button" onClick={() => void confirmarExclusaoUsuario()} disabled={excluindoUsuario}>{excluindoUsuario ? "Excluindo..." : "Excluir usuário"}</button></div></div>}
      </Modal>
    </div>
  );
}
