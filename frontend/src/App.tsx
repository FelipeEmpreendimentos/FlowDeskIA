import { Navigate, Route, Routes } from "react-router";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { SuperAdminLayout } from "./components/SuperAdminLayout";
import { SuperAdminProtectedRoute } from "./components/SuperAdminProtectedRoute";
import { Agenda } from "./pages/Agenda";
import { Atividades } from "./pages/Atividades";
import { Clientes } from "./pages/Clientes";
import { Configuracoes } from "./pages/Configuracoes";
import { Conversas } from "./pages/Conversas";
import { Dashboard } from "./pages/Dashboard";
import { Equipe } from "./pages/Equipe";
import { Financeiro } from "./pages/Financeiro";
import { Login } from "./pages/Login";
import { PlanoConsumo } from "./pages/PlanoConsumo";
import { RecuperarSenha } from "./pages/RecuperarSenha";
import { RedefinirSenha } from "./pages/RedefinirSenha";
import { Relatorios } from "./pages/Relatorios";
import { Servicos } from "./pages/Servicos";
import { SuperAdminAuditoria } from "./pages/SuperAdminAuditoria";
import { SuperAdminDashboard } from "./pages/SuperAdminDashboard";
import { SuperAdminEmpresaDetalhe } from "./pages/SuperAdminEmpresaDetalhe";
import { SuperAdminEmpresas } from "./pages/SuperAdminEmpresas";
import { SuperAdminLogin } from "./pages/SuperAdminLogin";
import { SuperAdminPlanos } from "./pages/SuperAdminPlanos";
import { Veiculos } from "./pages/Veiculos";

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
        <Route path="/financeiro" element={<Financeiro />} />
        <Route path="/relatorios" element={<Relatorios />} />
        <Route path="/atividades" element={<Atividades />} />
        <Route path="/plano-consumo" element={<PlanoConsumo />} />
        <Route path="/clientes" element={<Clientes />} />
        <Route path="/veiculos" element={<Veiculos />} />
        <Route path="/servicos" element={<Servicos />} />
        <Route path="/conversas" element={<Conversas />} />
        <Route path="/equipe" element={<Equipe />} />
        <Route path="/configuracoes" element={<Configuracoes />} />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
