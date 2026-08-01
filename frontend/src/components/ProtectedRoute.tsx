import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router";
import { restoreRememberedSession } from "../services/api";
import { getToken } from "../services/auth";
import { LoadingState } from "./UI";

type AuthStatus = "checking" | "authenticated" | "unauthenticated";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(
    getToken() ? "authenticated" : "checking",
  );

  useEffect(() => {
    if (status !== "checking") return;

    let ativo = true;
    void restoreRememberedSession().then((restaurada) => {
      if (!ativo) return;
      setStatus(restaurada ? "authenticated" : "unauthenticated");
    });

    return () => {
      ativo = false;
    };
  }, [status]);

  if (status === "checking") {
    return (
      <main className="app-loading">
        <LoadingState label="Verificando sua sessão..." />
      </main>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return children;
}
