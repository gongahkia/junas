"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import CommandPalette from "./chat/CommandPalette";
import { addNotification } from "../lib/notification-store";
import { getBenchmarkLeaderboard, runBenchmark } from "../lib/api-client";
import { findShortcutForEvent, KEYBOARD_SHORTCUTS, SHORTCUT_BY_ID, type KeyboardActionId } from "../lib/keyboard";

type PaletteMode = "all" | "pages";

function onChatPage(): boolean {
  return window.location.pathname === "/chat";
}

function clickDocxExport(): boolean {
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>("button"));
  const button = buttons.find((candidate) => candidate.title === "Download as Microsoft Word document");
  button?.click();
  return Boolean(button);
}

export default function KeyboardHelpDialog() {
  const [helpOpen, setHelpOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteMode, setPaletteMode] = useState<PaletteMode>("all");

  const runAction = useCallback(async (id: KeyboardActionId) => {
    switch (id) {
      case "open-command-palette":
        setPaletteMode("all");
        setPaletteOpen(true);
        return;
      case "open-keyboard-help":
        setHelpOpen(true);
        return;
      case "focus-chat-input":
        if (onChatPage()) {
          window.dispatchEvent(new CustomEvent("junas:focus-chat-input"));
        } else {
          window.location.assign("/chat?focus=1");
        }
        return;
      case "new-chat":
        if (onChatPage()) {
          window.dispatchEvent(new CustomEvent("junas:new-chat"));
        } else {
          window.location.assign("/chat");
        }
        return;
      case "toggle-session-sidebar":
        document.documentElement.classList.toggle("focus-mode");
        window.dispatchEvent(new CustomEvent("junas:toggle-session-sidebar"));
        return;
      case "export-current-view-docx":
        if (!clickDocxExport()) addNotification("info", "Export unavailable", "This view has no DOCX export.");
        return;
      case "copy-last-assistant-response":
        window.dispatchEvent(new CustomEvent("junas:copy-last-assistant-response"));
        return;
      case "jump-to-page-palette":
        setPaletteMode("pages");
        setPaletteOpen(true);
        return;
      case "rerun-last-benchmark": {
        const leaderboard = await getBenchmarkLeaderboard();
        const [latest] = [...leaderboard.entries].sort((a, b) => Date.parse(b.finished_at) - Date.parse(a.finished_at));
        if (!latest) {
          addNotification("info", "No benchmark to re-run", "Run history is empty.");
          return;
        }
        const evaluators = Object.keys(latest.per_evaluator_mean);
        if (evaluators.length === 0) {
          addNotification("warning", "Cannot re-run benchmark", "Latest run has no evaluator metadata.");
          return;
        }
        const response = await runBenchmark({ workflow: latest.workflow, dataset: latest.dataset, evaluators, strict: latest.strict, max_concurrency: 1 });
        if (response.error) {
          addNotification("error", "Benchmark failed", response.error);
          return;
        }
        addNotification("success", "Benchmark re-run started", String(response.run_id || latest.workflow));
        return;
      }
    }
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const shortcut = findShortcutForEvent(event);
      if (!shortcut) return;
      event.preventDefault();
      void runAction(shortcut.id);
    };
    const onAction = (event: Event) => {
      const id = (event as CustomEvent).detail?.id as KeyboardActionId | undefined;
      if (id && SHORTCUT_BY_ID.has(id)) void runAction(id);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("junas:keyboard-action", onAction);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("junas:keyboard-action", onAction);
    };
  }, [runAction]);

  const rows = useMemo(() => KEYBOARD_SHORTCUTS, []);

  return (
    <>
      <CommandPalette
        isOpen={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelectCommand={(cmdId) => {
          if (onChatPage()) {
            window.dispatchEvent(new CustomEvent("junas:chat-command", { detail: { id: cmdId } }));
          } else {
            localStorage.setItem("junas_pending_chat_command", cmdId);
            window.location.assign("/chat");
          }
        }}
        onNewChat={() => void runAction("new-chat")}
        filterMode={paletteMode}
      />
      {helpOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Keyboard shortcuts"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 120,
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "center",
            padding: "12vh 1rem 1rem",
            background: "rgba(15,23,42,0.18)",
          }}
          onClick={() => setHelpOpen(false)}
        >
          <div
            style={{
              width: "min(720px, 100%)",
              maxHeight: "76vh",
              overflow: "auto",
              border: "1px solid #cbd5e1",
              borderRadius: "0.5rem",
              background: "#fff",
              boxShadow: "0 18px 50px rgba(15,23,42,0.22)",
            }}
            onClick={(event) => event.stopPropagation()}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.8rem 1rem", borderBottom: "1px solid #e2e8f0" }}>
              <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700 }}>Keyboard shortcuts</h2>
              <button type="button" onClick={() => setHelpOpen(false)} style={{ border: "none", background: "transparent", cursor: "pointer", fontSize: "1.25rem", lineHeight: 1 }} aria-label="Close keyboard shortcuts">&times;</button>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
              <thead>
                <tr style={{ background: "#f8fafc", color: "#475569" }}>
                  <th style={th}>Action</th>
                  <th style={th}>Mac</th>
                  <th style={th}>Windows/Linux</th>
                  <th style={th}>Scope</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((shortcut) => (
                  <tr key={shortcut.id}>
                    <td style={td}>
                      <strong style={{ display: "block", color: "#0f172a" }}>{shortcut.label}</strong>
                      <span style={{ color: "#64748b" }}>{shortcut.description}</span>
                    </td>
                    <td style={td}><kbd style={kbd}>{shortcut.mac}</kbd></td>
                    <td style={td}><kbd style={kbd}>{shortcut.windows}</kbd></td>
                    <td style={td}>{shortcut.category}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

const th: React.CSSProperties = { padding: "0.55rem 0.75rem", textAlign: "left", borderBottom: "1px solid #e2e8f0", fontWeight: 700 };
const td: React.CSSProperties = { padding: "0.65rem 0.75rem", borderBottom: "1px solid #f1f5f9", verticalAlign: "top" };
const kbd: React.CSSProperties = { display: "inline-flex", minWidth: "3.7rem", justifyContent: "center", border: "1px solid #d6d3d1", borderBottomWidth: "2px", borderRadius: "0.35rem", padding: "0.18rem 0.45rem", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: "0.76rem", background: "#fafaf9", color: "#1c1917" };
