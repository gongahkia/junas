import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App.tsx";
import { config } from "./config";
import { initClientObservability } from "@/lib/observability";

initClientObservability();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename={config.app.basePath}>
      <App />
    </BrowserRouter>
  </StrictMode>
);
