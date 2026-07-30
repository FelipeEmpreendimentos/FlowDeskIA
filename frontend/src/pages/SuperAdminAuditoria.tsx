import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { superAdminApiRequest } from "../services/superAdminApi";
import type { SuperAdminLog } from "../types/superAdmin";
import { formatDateTime } from "../utils/format";

export function SuperAdminAuditoria() {
  const [logs, setLogs] = useState<SuperAdminLog[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    async function carregar() {
      try {
        setLogs(await superAdminApiRequest<SuperAdminLog[]>("/auditoria?limit=200"));
      } catch (error) {
        setErro(error instanceof Error ? error.message : "Não foi possível carregar a auditoria.");
      } finally {
        setCarregando(false);
      }
    }
    void carregar();
  }, []);

  return (
    <div className="super-admin-page">
      <header className="super-admin-page-header">
        <div>
          <span>Segurança da plataforma</span>
          <h1>Auditoria</h1>
          <p>Todas as alterações críticas do Super Admin ficam registradas.</p>
        </div>
        <span className="super-admin-header-icon"><Icon name="lock" /></span>
      </header>

      {erro && <div className="super-admin-alert error">{erro}</div>}
      {carregando ? (
        <div className="super-admin-state">Carregando auditoria...</div>
      ) : logs.length === 0 ? (
        <div className="super-admin-state">Nenhuma ação registrada ainda.</div>
      ) : (
        <section className="super-admin-card super-admin-audit-list">
          {logs.map((log) => (
            <article key={log.id}>
              <span><Icon name="clock" size={17} /></span>
              <div>
                <strong>{log.acao.replaceAll("_", " ")}</strong>
                <p>
                  {log.entidade ? `${log.entidade} #${log.entidade_id ?? "—"}` : "Plataforma"}
                  {log.empresa_id ? ` · Empresa #${log.empresa_id}` : ""}
                </p>
                <small>{formatDateTime(log.created_at)}{log.ip ? ` · IP ${log.ip}` : ""}</small>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
