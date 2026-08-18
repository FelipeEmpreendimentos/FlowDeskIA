import { Navigate, Route, Routes } from "react-router";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { SuperAdminLayout } from "./components/SuperAdminLayout";
import { SuperAdminProtectedRoute } from "./components/SuperAdminProtectedRoute";
import { Agenda } from "./pages/Agenda";
import { Atividades } from "./pages/Atividades";
import { ChatInterno } from "./pages/ChatInterno";
import { Clientes } from "./pages/Clientes";
import { ConfiguracaoAcessos } from "./pages/ConfiguracaoAcessos";
import { ConfiguracaoAgenda } from "./pages/ConfiguracaoAgenda";
import { ConfiguracaoIA } from "./pages/ConfiguracaoIA";
import { ConfiguracaoRelatorios } from "./pages/ConfiguracaoRelatorios";
import { Configuracoes } from "./pages/Configuracoes";
import { ConfiguracoesHub } from "./pages/ConfiguracoesHub";
import { Conversas } from "./pages/Conversas";
import { Dashboard } from "./pages/Dashboard";
import { Equipe } from "./pages/Equipe";
import { Financeiro } from "./pages/Financeiro";
import { HistoricoConversas } from "./pages/HistoricoConversas";
import { Login } from "./pages/Login";
import { Notificacoes } from "./pages/Notificacoes";
import { PlanoConsumo } from "./pages/PlanoConsumo";
import { RecuperarSenha } from "./pages/RecuperarSenha";
import { RedefinirSenha } from "./pages/RedefinirSenha";
import { Relatorios } from "./pages/Relatorios";
import { Servicos } from "./pages/Servicos";
import { SuperAdminAuditoria } from "./pages/SuperAdminAuditoria";
import { SuperAdminDashboard } from "./pages/SuperAdminDashboard";
import { SuperAdminEmpresaDetalhe } from "./pages/SuperAdminEmpresaDetalhe";
import { SuperAdminEmpresas } from "./pages/SuperAdminEmpresas";
import { SuperAdminIASimulatorGuided } from "./pages/SuperAdminIASimulatorGuided";
import { SuperAdminLogin } from "./pages/SuperAdminLogin";
import { SuperAdminPlanos } from "./pages/SuperAdminPlanos";
import { Veiculos } from "./pages/Veiculos";
import "./super-admin-ai-simulator.css";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/recuperar-senha" element={<RecuperarSenha />} />
      <Route path="/redefinir-senha" element={<RedefinirSenha />} />
      <Route path="/super-admin/login" element={<SuperAdminLogin />} />

      <Route
        path="/super-admin"
        element={
          <SuperAdminProtectedRoute>
            <SuperAdminLayout />
          </SuperAdminProtectedRoute>
        }
      >
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<SuperAdminDashboard />} />
        <Route path="empresas" element={<SuperAdminEmpresas />} />
        <Route path="empresas/:empresaId" element={<SuperAdminEmpresaDetalhe />} />
        <Route path="simulador-ia" element={<SuperAdminIASimulatorGuided />} />
        <Route path="planos" element={<SuperAdminPlanos />} />
        <Route path="auditoria" element={<SuperAdminAuditoria />} />
      </Route>

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/agenda" element={<Agenda />} />
        <Route path="/chat-interno" element={<ChatInterno />} />
        <Route path="/financeiro" element={<Financeiro />} />
        <Route path="/relatorios" element={<Relatorios />} />
        <Route path="/atividades" element={<Atividades />} />
        <Route path="/plano-consumo" element={<PlanoConsumo />} />
        <Route path="/notificacoes" element={<Notificacoes />} />
        <Route path="/clientes" element={<Clientes />} />
        <Route path="/veiculos" element={<Veiculos />} />
        <Route path="/servicos" element={<Servicos />} />
        <Route path="/conversas" element={<Conversas />} />
        <Route path="/historico-conversas" element={<HistoricoConversas />} />
        <Route path="/equipe" element={<Equipe />} />
        <Route path="/configuracoes" element={<ConfiguracoesHub />} />
        <Route path="/configuracoes/dados" element={<Configuracoes />} />
        <Route path="/configuracoes/agenda" element={<ConfiguracaoAgenda />} />
        <Route path="/configuracoes/ia" element={<ConfiguracaoIA />} />
        <Route path="/configuracoes/acessos" element={<ConfiguracaoAcessos />} />
        <Route path="/configuracoes/relatorios" element={<ConfiguracaoRelatorios />} />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
