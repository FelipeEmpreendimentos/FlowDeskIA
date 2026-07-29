import type { ReactNode } from "react";
import { Navigate } from "react-router";
import { getToken } from "../services/auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
