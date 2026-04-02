"use client";
import { useState, useEffect } from "react";
import { listJurisdictions } from "../../lib/api-client";

const PROVIDERS = ["claude", "openai", "gemini", "ollama", "lmstudio"];

type Jurisdiction = { id: string; name: string; short_name: string; system_prompt_addition: string };

export default function SettingsPage() {
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([]);
  const [selectedJurisdiction, setSelectedJurisdiction] = useState("");

  useEffect(() => {
    const loaded: Record<string, string> = {};
    PROVIDERS.forEach((p) => { loaded[p] = localStorage.getItem(`junas_apikey_${p}`) || ""; });
    setKeys(loaded);
    setSelectedJurisdiction(localStorage.getItem("junas_jurisdiction") || "");
    listJurisdictions().then((data) => setJurisdictions(Array.isArray(data) ? data : [])).catch(() => {});
  }, []);

  const save = () => {
    PROVIDERS.forEach((p) => {
      if (keys[p]) localStorage.setItem(`junas_apikey_${p}`, keys[p]);
      else localStorage.removeItem(`junas_apikey_${p}`);
    });
    // save jurisdiction
    if (selectedJurisdiction) {
      localStorage.setItem("junas_jurisdiction", selectedJurisdiction);
      const j = jurisdictions.find((x) => x.id === selectedJurisdiction);
      if (j?.system_prompt_addition) localStorage.setItem("junas_jurisdiction_prompt", j.system_prompt_addition);
      else localStorage.removeItem("junas_jurisdiction_prompt");
    } else {
      localStorage.removeItem("junas_jurisdiction");
      localStorage.removeItem("junas_jurisdiction_prompt");
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div>
      <h2>Settings</h2>
      <p className="meta-line">Configure API keys and provider settings. Keys are stored in your browser only (never sent to the server for storage).</p>
      <div style={{ maxWidth: "500px" }}>
        {PROVIDERS.map((p) => (
          <div key={p} style={{ marginBottom: "0.75rem" }}>
            <label style={{ fontSize: "0.8rem", fontWeight: 700, textTransform: "capitalize" }}>{p} API Key</label>
            <input type="password" value={keys[p] || ""} onChange={(e) => setKeys({ ...keys, [p]: e.target.value })} placeholder={p === "ollama" || p === "lmstudio" ? "Not required (local)" : `Enter ${p} API key`} style={{ width: "100%", padding: "0.4rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", font: "inherit", marginTop: "0.2rem" }} />
          </div>
        ))}
        <div style={{ marginBottom: "0.75rem", borderTop: "1px solid #e2e8f0", paddingTop: "0.75rem" }}>
          <label style={{ fontSize: "0.8rem", fontWeight: 700 }}>Default Jurisdiction</label>
          <select value={selectedJurisdiction} onChange={(e) => setSelectedJurisdiction(e.target.value)} style={{ width: "100%", padding: "0.4rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", font: "inherit", marginTop: "0.2rem" }}>
            <option value="">None (general)</option>
            {jurisdictions.map((j) => <option key={j.id} value={j.id}>{j.name} ({j.short_name})</option>)}
          </select>
          <p style={{ fontSize: "0.75rem", color: "#64748b", margin: "0.2rem 0 0" }}>Sets jurisdiction-specific system prompt for AI chat</p>
        </div>
        <button type="button" onClick={save} style={{ padding: "0.5rem 1.2rem", borderRadius: "0.5rem", border: "none", background: "#0f172a", color: "#fff", cursor: "pointer", font: "inherit" }}>
          {saved ? "Saved!" : "Save All"}
        </button>
      </div>
    </div>
  );
}
