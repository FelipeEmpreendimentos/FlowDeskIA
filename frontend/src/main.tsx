import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./App";
import "./index.css";
import "./permission-ui.css";
import "./financeiro.css";
import "./relatorios.css";
import "./engagement.css";
import "./mobile-release.css";
import "./navigation-chat.css";
import "./navigation-toggle-fixes.css";
import "./chat-workspace.css";
import "./chat-workspace-refinement.css";
import "./remember-session.css";
import "./super-admin.css";
import "./super-admin-enhancements.css";
import "./review-polish.css";
import "./access-settings.css";
import "./base-version-refinements.css";
import "./fine-tuning.css";
import "./final-visual-adjustments.css";
import "./permission-behavior.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
