import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../services/api";

export type AttendanceStatus = "DISPONIVEL" | "AUSENTE" | "OFFLINE";

interface PresenceResponse {
  user_id: number;
  empresa_id: number;
  status: AttendanceStatus;
  status_efetivo: AttendanceStatus;
  heartbeat_at: string | null;
  last_assignment_at: string | null;
}

const labels: Record<AttendanceStatus, string> = {
  DISPONIVEL: "Online",
  AUSENTE: "Ausente",
  OFFLINE: "Offline",
};

const descriptions: Record<AttendanceStatus, string> = {
  DISPONIVEL: "Recebe novos atendimentos distribuídos automaticamente.",
  AUSENTE: "Não recebe novas distribuições automáticas, mas pode atender e controlar conversas normalmente.",
  OFFLINE: "Não recebe novos atendimentos e não pode responder clientes.",
};

const attendanceStatuses: AttendanceStatus[] = [
  "DISPONIVEL",
  "AUSENTE",
  "OFFLINE",
];

export function useAttendancePresence(enabled: boolean) {
  const [status, setStatusState] = useState<AttendanceStatus>("OFFLINE");
  const [effectiveStatus, setEffectiveStatus] =
    useState<AttendanceStatus>("OFFLINE");
  const [loading, setLoading] = useState(enabled);
  const [changing, setChanging] = useState(false);

  const applyResponse = useCallback((value: PresenceResponse) => {
    setStatusState(value.status);
    setEffectiveStatus(value.status_efetivo);
  }, []);

  useEffect(() => {
    if (!enabled) {
      delete document.documentElement.dataset.attendanceStatus;
      return;
    }
    document.documentElement.dataset.attendanceStatus = effectiveStatus;
    return () => {
      delete document.documentElement.dataset.attendanceStatus;
    };
  }, [effectiveStatus, enabled]);

  const heartbeat = useCallback(async () => {
    if (!enabled) return;
    try {
      const value = await apiRequest<PresenceResponse>(
        "/atendimento-equipe/heartbeat",
        { method: "POST" },
      );
      applyResponse(value);
    } catch {
      // A expiração/autenticação continua sendo tratada pelo fluxo normal do app.
    }
  }, [applyResponse, enabled]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    setLoading(true);
    let active = true;
    async function load() {
      try {
        const value = await apiRequest<PresenceResponse>("/atendimento-equipe/me");
        if (active) applyResponse(value);
      } catch {
        if (active) {
          setStatusState("OFFLINE");
          setEffectiveStatus("OFFLINE");
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();

    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void heartbeat();
    }, 30000);

    const onVisibility = () => {
      if (document.visibilityState === "visible") void heartbeat();
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      active = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [applyResponse, enabled, heartbeat]);

  const changeStatus = useCallback(
    async (next: AttendanceStatus) => {
      if (!enabled || changing) return;
      setChanging(true);
      try {
        const value = await apiRequest<PresenceResponse>("/atendimento-equipe/me", {
          method: "PATCH",
          body: JSON.stringify({ status: next }),
        });
        applyResponse(value);
        window.dispatchEvent(
          new CustomEvent("flowdesk:attendance-presence", {
            detail: { status: value.status, effectiveStatus: value.status_efetivo },
          }),
        );
      } finally {
        setChanging(false);
      }
    },
    [applyResponse, changing, enabled],
  );

  return {
    status,
    effectiveStatus,
    loading,
    changing,
    changeStatus,
  };
}

export function AttendancePresenceSelect({
  status,
  effectiveStatus,
  loading,
  changing,
  compact = false,
  onChange,
}: {
  status: AttendanceStatus;
  effectiveStatus: AttendanceStatus;
  loading: boolean;
  changing: boolean;
  compact?: boolean;
  onChange: (value: AttendanceStatus) => void;
}) {
  const detailsRef = useRef<HTMLDetailsElement>(null);

  if (!compact) {
    return (
      <details
        ref={detailsRef}
        className={`attendance-presence-control attendance-presence-user-menu attendance-presence-${effectiveStatus.toLowerCase()}`}
        title={descriptions[effectiveStatus]}
      >
        <summary
          className="attendance-presence-user-trigger"
          aria-label={`Alterar status de atendimento. Status atual: ${labels[effectiveStatus]}`}
        />
        <div className="attendance-presence-user-options" role="menu">
          {attendanceStatuses.map((value) => (
            <button
              className={`attendance-presence-user-option attendance-presence-user-option-${value.toLowerCase()} ${status === value ? "active" : ""}`}
              type="button"
              role="menuitem"
              key={value}
              disabled={loading || changing}
              title={descriptions[value]}
              onClick={() => {
                if (detailsRef.current) detailsRef.current.open = false;
                if (value !== status) onChange(value);
              }}
            >
              <span className="attendance-presence-option-dot" aria-hidden="true" />
              <span>{labels[value]}</span>
              {status === value && (
                <span className="attendance-presence-option-check" aria-hidden="true">
                  ✓
                </span>
              )}
            </button>
          ))}
        </div>
      </details>
    );
  }

  return (
    <label
      className={`attendance-presence-control attendance-presence-${effectiveStatus.toLowerCase()} attendance-presence-compact`}
      title={descriptions[effectiveStatus]}
    >
      <span className="attendance-presence-dot" aria-hidden="true" />
      <select
        aria-label="Status de atendimento"
        value={status}
        disabled={loading || changing}
        onChange={(event) => onChange(event.target.value as AttendanceStatus)}
      >
        {attendanceStatuses.map((value) => (
          <option value={value} key={value}>
            {labels[value]}
          </option>
        ))}
      </select>
    </label>
  );
}
