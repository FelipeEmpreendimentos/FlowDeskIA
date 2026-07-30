import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { getSuperAdminToken } from "../services/superAdminAuth";

interface Props {
  children: ReactNode;
}

export function SuperAdminProtectedRoute({ children }: Props) {
  const location = useLocation();
  if (!getSuperAdminToken()) {
    return (
      <Navigate
        to="/super-admin/login"
        state={{ from: location.pathname }}
        replace
      />
    );
  }
  return children;
}
