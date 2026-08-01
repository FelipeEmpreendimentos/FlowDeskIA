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
import "./super-admin.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
