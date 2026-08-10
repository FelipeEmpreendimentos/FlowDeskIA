export interface ReportSettings {
  usar_financeiro: boolean;
}

const REPORTS_FROM_APPOINTMENTS_CLASS = "reports-from-finalized-appointments";

export function applyReportFinanceVisibility(usarFinanceiro: boolean): void {
  document.documentElement.classList.toggle(
    REPORTS_FROM_APPOINTMENTS_CLASS,
    !usarFinanceiro,
  );
}
