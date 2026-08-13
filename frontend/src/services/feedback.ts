import {
  APP_TOAST_EVENT,
  type AppToastEventDetail,
  type AppToastType,
} from "./api";

export function showAppToast(
  message: string,
  options: {
    type?: AppToastType;
    title?: string;
  } = {},
): void {
  const type = options.type ?? "success";
  const defaultTitles: Record<AppToastType, string> = {
    success: "Sucesso",
    error: "Não foi possível concluir",
    warning: "Atenção",
    info: "Informação",
  };

  const detail: AppToastEventDetail = {
    type,
    title: options.title ?? defaultTitles[type],
    message,
  };

  window.dispatchEvent(
    new CustomEvent<AppToastEventDetail>(APP_TOAST_EVENT, { detail }),
  );
}
