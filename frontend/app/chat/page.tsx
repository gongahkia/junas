"use client";
import { useState, useRef, useEffect, useCallback, lazy, Suspense } from "react";
import type { NodeMap, TreeMessage, MessageRole } from "../../lib/chat-tree";
import { createId, getLinearHistory, getBranchSiblings, addChild, findLeaves } from "../../lib/chat-tree";
import { parseDocument } from "../../lib/api-client";
import { handleCommand } from "../../lib/commands/command-handler";
import { saveConversation, loadConversation, generateConversationId } from "../../lib/conversation-store";
import { useKeyboardShortcuts } from "../../lib/use-keyboard-shortcuts";
import TokenCounter from "../../components/chat/TokenCounter";
import CommandSuggestions, { COMMANDS } from "../../components/chat/CommandSuggestions";
import ConversationHistory from "../../components/chat/ConversationHistory";

const LegalMarkdownRenderer = lazy(() => import("../../components/chat/LegalMarkdownRenderer"));
const GitTree = lazy(() => import("../../components/chat/GitTree"));
const CommandPalette = lazy(() => import("../../components/chat/CommandPalette"));

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Tab = "chat" | "tree";

export default function ChatPage() {
  // tree state
  const [nodeMap, setNodeMap] = useState<NodeMap>({});
  const [currentLeafId, setCurrentLeafId] = useState("");
  const [conversationId, setConversationId] = useState("");
  // UI state
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState("claude");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [showSettings, setShowSettings] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  // command palette + suggestions
  const [cmdOpen, setCmdOpen] = useState(false);
  const [cmdQuery, setCmdQuery] = useState("");
  const [cmdIndex, setCmdIndex] = useState(0);
  const [paletteOpen, setPaletteOpen] = useState(false);
  // history
  const [historyOpen, setHistoryOpen] = useState(false);
  // doc upload
  const [pendingFile, setPendingFile] = useState<{ name: string; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // refs
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const startTimeRef = useRef(0);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const messages = currentLeafId ? getLinearHistory(nodeMap, currentLeafId) : [];

  // auto-scroll
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length, streaming]);
  // load API key
  useEffect(() => { setApiKey(localStorage.getItem(`junas_apikey_${provider}`) || ""); }, [provider]);
  // load jurisdiction system prompt
  useEffect(() => {
    const stored = localStorage.getItem("junas_jurisdiction_prompt");
    if (stored && !systemPrompt) setSystemPrompt(stored);
  }, []);

  // persistence: auto-save on tree changes (debounced)
  useEffect(() => {
    if (!conversationId || Object.keys(nodeMap).length === 0) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => saveConversation(conversationId, nodeMap, currentLeafId), 500);
  }, [nodeMap, currentLeafId, conversationId]);

  // keyboard shortcuts
  useKeyboardShortcuts({
    onCommandPalette: () => setPaletteOpen(true),
    onNewChat: () => newChat(),
  });

  // --- streaming send ---
  const sendMessage = async (overrideContent?: string) => {
    const rawText = (overrideContent ?? input).trim();
    if (!rawText || streaming) return;
    if (!overrideContent) setInput("");
    // attach document if pending
    let text = rawText;
    if (pendingFile && !overrideContent) {
      text = `[Document: ${pendingFile.name}]\n\n${pendingFile.text}\n\n---\n\n${rawText}`;
      setPendingFile(null);
    }
    // ensure conversation ID
    if (!conversationId) setConversationId(generateConversationId());
    let map = nodeMap;
    let parentId = currentLeafId;
    // if tree is empty, create root user message
    if (!parentId) {
      const root: TreeMessage = { id: createId(), role: "user", content: text, childrenIds: [], timestamp: Date.now() };
      map = { [root.id]: root };
      parentId = root.id;
    } else {
      const userMsg: TreeMessage = { id: createId(), role: "user", content: text, parentId, childrenIds: [], timestamp: Date.now() };
      map = addChild(map, parentId, userMsg);
      parentId = userMsg.id;
    }
    setNodeMap(map);
    setCurrentLeafId(parentId);
    // check for command
    const cmdResult = await handleCommand(text);
    if (cmdResult.isCommand) {
      const asstId = createId();
      const asst: TreeMessage = { id: asstId, role: "assistant", content: cmdResult.response || "", parentId, childrenIds: [], timestamp: Date.now() };
      const newMap = addChild(map, parentId, asst);
      setNodeMap(newMap);
      setCurrentLeafId(asstId);
      return;
    }
    // streaming AI response
    const asstId = createId();
    const asstMsg: TreeMessage = { id: asstId, role: "assistant", content: "", parentId, childrenIds: [], timestamp: Date.now() };
    map = addChild(map, parentId, asstMsg);
    setNodeMap(map);
    setCurrentLeafId(asstId);
    setStreaming(true);
    startTimeRef.current = Date.now();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const history = getLinearHistory(map, asstId).slice(0, -1);
      const resp = await fetch(`${API_BASE}/api/v1/chat/stream`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, model: model || undefined, messages: history.map((m) => ({ role: m.role, content: m.content })), api_key: apiKey || localStorage.getItem(`junas_apikey_${provider}`) || "", system_prompt: systemPrompt || undefined, max_tokens: 4096 }),
        signal: controller.signal,
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const reader = resp.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = "", accumulated = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try { const ev = JSON.parse(line.slice(6)); if (ev.error) throw new Error(ev.error); if (ev.delta) { accumulated += ev.delta; setNodeMap((prev) => ({ ...prev, [asstId]: { ...prev[asstId], content: accumulated, responseTimeMs: Date.now() - startTimeRef.current } })); } } catch {}
        }
      }
      setNodeMap((prev) => ({ ...prev, [asstId]: { ...prev[asstId], content: accumulated, responseTimeMs: Date.now() - startTimeRef.current } }));
    } catch (err: any) {
      if (err.name !== "AbortError") setNodeMap((prev) => ({ ...prev, [asstId]: { ...prev[asstId], content: `Error: ${err.message}` } }));
    } finally { setStreaming(false); abortRef.current = null; }
  };

  const stopGeneration = () => { abortRef.current?.abort(); };
  const newChat = () => { setNodeMap({}); setCurrentLeafId(""); setConversationId(""); };

  // edit → new branch
  const startEdit = (msgId: string) => { const msg = nodeMap[msgId]; if (msg?.role === "user") { setEditingId(msgId); setEditContent(msg.content); } };
  const saveEdit = () => {
    if (!editingId || !nodeMap[editingId]?.parentId) return;
    const edited: TreeMessage = { id: createId(), role: "user", content: editContent.trim(), parentId: nodeMap[editingId].parentId, childrenIds: [], timestamp: Date.now() };
    const newMap = addChild(nodeMap, nodeMap[editingId].parentId!, edited);
    setNodeMap(newMap); setCurrentLeafId(edited.id); setEditingId(null); setEditContent("");
    setTimeout(() => sendMessage(editContent.trim()), 50);
  };

  // branch navigation
  const switchBranch = (msgId: string, dir: "prev" | "next") => {
    const sibs = getBranchSiblings(nodeMap, msgId);
    const idx = sibs.indexOf(msgId) + (dir === "prev" ? -1 : 1);
    if (idx < 0 || idx >= sibs.length) return;
    let leaf = sibs[idx];
    while (nodeMap[leaf]?.childrenIds.length > 0) leaf = nodeMap[leaf].childrenIds[0];
    setCurrentLeafId(leaf);
  };

  const onSelectNode = (nodeId: string) => {
    let leaf = nodeId;
    while (nodeMap[leaf]?.childrenIds.length > 0) leaf = nodeMap[leaf].childrenIds[0];
    setCurrentLeafId(leaf); setActiveTab("chat");
  };

  // load conversation from history
  const loadFromHistory = (id: string) => {
    const conv = loadConversation(id);
    if (!conv) return;
    setNodeMap(conv.nodeMap); setCurrentLeafId(conv.currentLeafId); setConversationId(id);
  };

  // doc upload handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      if (file.name.endsWith(".txt") || file.name.endsWith(".md")) {
        const text = await file.text();
        setPendingFile({ name: file.name, text });
      } else {
        const result = await parseDocument(file);
        setPendingFile({ name: result.filename || file.name, text: result.text });
      }
    } catch (err: any) { setPendingFile({ name: file.name, text: `[Error parsing: ${err.message}]` }); }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // export chat
  const exportChat = (format: "md" | "txt") => {
    const history = currentLeafId ? getLinearHistory(nodeMap, currentLeafId) : [];
    if (history.length === 0) return;
    const content = format === "md"
      ? `# Chat Export\n\n${history.map((m) => `## ${m.role === "user" ? "You" : "Junas"}\n\n${m.content}\n`).join("\n---\n\n")}`
      : history.map((m) => `[${m.role}]\n${m.content}`).join("\n\n---\n\n");
    const blob = new Blob([content], { type: format === "md" ? "text/markdown" : "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `chat-export-${Date.now()}.${format}`; a.click();
    URL.revokeObjectURL(url);
  };

  // command suggestions
  const onInputChange = (val: string) => {
    setInput(val);
    if (val.startsWith("/") && !val.includes(" ")) { setCmdOpen(true); setCmdQuery(val.slice(1)); setCmdIndex(0); } else { setCmdOpen(false); }
  };
  const onCommandSelect = (cmdId: string) => { setInput(`/${cmdId} `); setCmdOpen(false); setPaletteOpen(false); };
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (cmdOpen) {
      if (e.key === "ArrowDown") { e.preventDefault(); setCmdIndex((i) => i + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setCmdIndex((i) => Math.max(0, i - 1)); }
      else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        const matches = COMMANDS.filter((c) => c.id.includes(cmdQuery) || c.label.toLowerCase().includes(cmdQuery.toLowerCase()));
        if (matches[cmdIndex]) onCommandSelect(matches[cmdIndex].id);
      } else if (e.key === "Escape") setCmdOpen(false);
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const leaves = findLeaves(nodeMap);

  return (
    <div>
      {/* header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem", flexWrap: "wrap", gap: "0.3rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <h2 style={{ margin: 0 }}>AI Chat</h2>
          {leaves.length > 1 && <span className="badge muted">{leaves.length} branches</span>}
        </div>
        <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
          {(["chat", "tree"] as Tab[]).map((t) => (
            <button key={t} type="button" onClick={() => setActiveTab(t)} style={{ padding: "0.25rem 0.6rem", borderRadius: "0.5rem", border: activeTab === t ? "2px solid #1d4ed8" : "1px solid #94a3b8", background: activeTab === t ? "#dbeafe" : "#f8fafc", cursor: "pointer", fontWeight: activeTab === t ? 700 : 400, textTransform: "capitalize", fontSize: "0.78rem" }}>{t === "tree" ? "Git Graph" : t}</button>
          ))}
          <button type="button" onClick={newChat} style={{ padding: "0.25rem 0.6rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", background: "#f8fafc", cursor: "pointer", fontSize: "0.78rem" }}>New</button>
          <button type="button" onClick={() => setHistoryOpen(true)} style={{ padding: "0.25rem 0.6rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", background: "#f8fafc", cursor: "pointer", fontSize: "0.78rem" }}>History</button>
          <button type="button" onClick={() => exportChat("md")} style={{ padding: "0.25rem 0.6rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", background: "#f8fafc", cursor: "pointer", fontSize: "0.78rem" }}>Export</button>
          <button type="button" onClick={() => setShowSettings(!showSettings)} style={{ padding: "0.25rem 0.6rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", background: "#f8fafc", cursor: "pointer", fontSize: "0.78rem" }}>{showSettings ? "Hide" : "Settings"}</button>
        </div>
      </div>
      {/* provider bar */}
      <div style={{ display: "flex", gap: "0.4rem", marginBottom: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
        <select value={provider} onChange={(e) => setProvider(e.target.value)} style={{ padding: "0.3rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", fontSize: "0.82rem" }}>
          <option value="claude">Claude</option><option value="openai">OpenAI</option><option value="gemini">Gemini</option><option value="ollama">Ollama</option><option value="lmstudio">LM Studio</option>
        </select>
        <input placeholder="Model (optional)" value={model} onChange={(e) => setModel(e.target.value)} style={{ padding: "0.3rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", width: "150px", fontSize: "0.82rem" }} />
        <span style={{ fontSize: "0.72rem", color: "#64748b" }}>/ for commands &middot; Cmd+K palette</span>
      </div>
      {/* settings */}
      {showSettings && (
        <div className="result-card" style={{ marginBottom: "0.6rem" }}>
          <div style={{ display: "grid", gap: "0.35rem" }}>
            <label style={{ fontSize: "0.78rem", fontWeight: 600 }}>API Key ({provider})</label>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Paste API key" style={{ flex: 1, padding: "0.35rem", borderRadius: "0.5rem", border: "1px solid #94a3b8" }} />
              <button type="button" onClick={() => { if (apiKey) localStorage.setItem(`junas_apikey_${provider}`, apiKey); }} style={{ padding: "0.35rem 0.5rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", background: "#0f172a", color: "#fff", cursor: "pointer" }}>Save</button>
            </div>
            <label style={{ fontSize: "0.78rem", fontWeight: 600 }}>System Prompt</label>
            <textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} placeholder="Optional system prompt..." rows={2} style={{ padding: "0.35rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", resize: "vertical" }} />
          </div>
        </div>
      )}
      {/* main content */}
      {activeTab === "chat" ? (
        <>
          <div className="chat-thread" style={{ maxHeight: "58vh", overflowY: "auto", marginBottom: "0.6rem" }}>
            {messages.map((m) => {
              const sibs = getBranchSiblings(nodeMap, m.id);
              const sibIdx = sibs.indexOf(m.id);
              const hasBranches = sibs.length > 1;
              return (
                <div key={m.id} className={`chat-message ${m.role === "user" ? "chat-user" : "chat-assistant"}`}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.15rem" }}>
                    <strong style={{ fontSize: "0.78rem" }}>{m.role === "user" ? "You" : "Junas"}</strong>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                      {hasBranches && (
                        <div style={{ display: "flex", alignItems: "center", gap: "0.1rem", fontSize: "0.68rem", color: "#64748b" }}>
                          <button type="button" onClick={() => switchBranch(m.id, "prev")} disabled={sibIdx === 0} style={{ background: "none", border: "none", cursor: sibIdx === 0 ? "default" : "pointer", color: sibIdx === 0 ? "#cbd5e1" : "#3b82f6", fontSize: "0.78rem", padding: "0 0.1rem" }}>&lt;</button>
                          <span style={{ fontFamily: "monospace" }}>{sibIdx + 1}/{sibs.length}</span>
                          <button type="button" onClick={() => switchBranch(m.id, "next")} disabled={sibIdx === sibs.length - 1} style={{ background: "none", border: "none", cursor: sibIdx === sibs.length - 1 ? "default" : "pointer", color: sibIdx === sibs.length - 1 ? "#cbd5e1" : "#3b82f6", fontSize: "0.78rem", padding: "0 0.1rem" }}>&gt;</button>
                        </div>
                      )}
                      {m.role === "user" && !editingId && <button type="button" onClick={() => startEdit(m.id)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.68rem", color: "#3b82f6" }}>Edit</button>}
                      <button type="button" onClick={() => navigator.clipboard.writeText(m.content)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.68rem", color: "#64748b" }}>Copy</button>
                    </div>
                  </div>
                  {editingId === m.id ? (
                    <div style={{ marginTop: "0.2rem" }}>
                      <textarea value={editContent} onChange={(e) => setEditContent(e.target.value)} rows={3} style={{ width: "100%", padding: "0.35rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", font: "inherit", resize: "vertical" }} />
                      <div style={{ display: "flex", gap: "0.25rem", marginTop: "0.2rem" }}>
                        <button type="button" onClick={saveEdit} style={{ padding: "0.25rem 0.5rem", borderRadius: "0.5rem", border: "none", background: "#1d4ed8", color: "#fff", cursor: "pointer", fontSize: "0.78rem" }}>Save & Branch</button>
                        <button type="button" onClick={() => setEditingId(null)} style={{ padding: "0.25rem 0.5rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", background: "#f8fafc", cursor: "pointer", fontSize: "0.78rem" }}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ marginTop: "0.15rem" }}>
                      {m.role === "assistant" ? (
                        <Suspense fallback={<div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>}><LegalMarkdownRenderer content={m.content} /></Suspense>
                      ) : <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>}
                    </div>
                  )}
                  {m.role === "assistant" && m.content && <TokenCounter content={m.content} isStreaming={streaming && m.id === currentLeafId} provider={provider} responseTimeMs={m.responseTimeMs} />}
                </div>
              );
            })}
            {streaming && <div className="meta-line" style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}><span>Streaming...</span><button type="button" onClick={stopGeneration} style={{ background: "none", border: "1px solid #ef4444", borderRadius: "0.5rem", color: "#ef4444", cursor: "pointer", padding: "0.1rem 0.4rem", fontSize: "0.72rem" }}>Stop</button></div>}
            <div ref={bottomRef} />
          </div>
          {/* pending file badge */}
          {pendingFile && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", marginBottom: "0.35rem", padding: "0.3rem 0.5rem", background: "#dbeafe", borderRadius: "0.5rem", fontSize: "0.78rem" }}>
              <span>📎 {pendingFile.name} ({pendingFile.text.length.toLocaleString()} chars)</span>
              <button type="button" onClick={() => setPendingFile(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "#64748b" }}>&times;</button>
            </div>
          )}
          {/* input area */}
          <div style={{ position: "relative" }}>
            <CommandSuggestions query={cmdQuery} onSelect={onCommandSelect} isOpen={cmdOpen} selectedIndex={cmdIndex} />
            <div style={{ display: "flex", gap: "0.4rem" }}>
              <input type="file" ref={fileInputRef} accept=".pdf,.docx,.txt,.md" onChange={handleFileUpload} style={{ display: "none" }} />
              <button type="button" onClick={() => fileInputRef.current?.click()} title="Attach document" style={{ padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", background: "#f8fafc", cursor: "pointer", fontSize: "1rem", alignSelf: "flex-end" }}>📎</button>
              <textarea value={input} onChange={(e) => onInputChange(e.target.value)} onKeyDown={onKeyDown} placeholder="Type a message or / for commands..." rows={1} style={{ flex: 1, padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", font: "inherit", resize: "none", minHeight: "40px", maxHeight: "180px", lineHeight: 1.4 }} />
              <button type="button" onClick={() => sendMessage()} disabled={streaming} style={{ padding: "0.5rem 0.9rem", borderRadius: "0.5rem", border: "none", background: "#0f172a", color: "#fff", cursor: streaming ? "not-allowed" : "pointer", font: "inherit", alignSelf: "flex-end" }}>{streaming ? "..." : "Send"}</button>
            </div>
          </div>
        </>
      ) : (
        <Suspense fallback={<div className="meta-line">Loading tree...</div>}><GitTree nodeMap={nodeMap} currentLeafId={currentLeafId} onSelectNode={onSelectNode} /></Suspense>
      )}
      {/* modals */}
      <Suspense fallback={null}><CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} onSelectCommand={onCommandSelect} onNewChat={newChat} /></Suspense>
      <ConversationHistory isOpen={historyOpen} onSelect={loadFromHistory} onClose={() => setHistoryOpen(false)} />
    </div>
  );
}
