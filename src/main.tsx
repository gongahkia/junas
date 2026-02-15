import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./app/globals.css";
if (!(window as any).__TAURI_INTERNALS__) {
  const root = document.getElementById("root")!;
  root.innerHTML = "";
  const container = document.createElement("div");
  container.style.cssText = "display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui,sans-serif;background:#0a0a0a;color:#e5e5e5;text-align:center;padding:2rem;";
  container.innerHTML = `<div><h1 style="font-size:1.5rem;margin-bottom:1rem;">Junas is a desktop application</h1><p style="color:#a3a3a3;">Please launch it via the Tauri app.</p></div>`;
  root.appendChild(container);
} else {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
