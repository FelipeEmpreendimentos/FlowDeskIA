import { Navigate, Route, Routes } from "react-router";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Agenda } from "./pages/Agenda";
import { Clientes } from "./pages/Clientes";
import { Configuracoes } from "./pages/Configuracoes";
import { Conversas } from "./pages/Conversas";
import { Dashboard } from "./pages/Dashboard";
import { Equipe } from "./pages/Equipe";
import { Login } from "./pages/Login";
import { RecuperarSenha } from "./pages/RecuperarSenha";
import { RedefinirSenha } from "./pages/RedefinirSenha";
import { Servicos } from "./pages/Servicos";
import { Veiculos } from "./pages/Veiculos";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/recuperar-senha" element={<RecuperarSenha />} />
      <Route path="/redefinir-senha" element={<RedefinirSenha />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/agenda" element={<Agenda />} />
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
