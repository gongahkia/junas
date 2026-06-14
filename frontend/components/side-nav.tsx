"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import ThemeToggle from "./theme-toggle";
import NotificationsPanel, { useUnreadCount } from "./notifications-panel";
import SessionSidebar from "./SessionSidebar";

const TOOL_LINKS = [
  { href: "/chat", label: "Copilot (Chat)" },
  { href: "/benchmarks", label: "SG-LegalBench" },
  { href: "/glossary", label: "Glossary" },
  { href: "/statutes", label: "Statutes" },
  { href: "/search", label: "Case Search" },
  { href: "/research", label: "Research" },
  { href: "/legal-sources", label: "Legal Sources" },
  { href: "/contracts", label: "Contracts" },
  { href: "/ner", label: "NER" },
  { href: "/compliance", label: "Compliance" },
  { href: "/batch-analysis", label: "Batch Analysis" },
  { href: "/clauses", label: "Clauses" },
  { href: "/templates", label: "Templates" },
  { href: "/documents", label: "Documents" },
];

export default function SideNav() {
  const pathname = usePathname();
  const [toolsOpen, setToolsOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeConvId, setActiveConvId] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);
  const unreadCount = useUnreadCount();

  useEffect(() => {
    const onActive = (e: Event) => setActiveConvId((e as CustomEvent).detail?.id || "");
    window.addEventListener("junas:active-conversation", onActive);
    return () => {
      window.removeEventListener("junas:active-conversation", onActive);
    };
  }, []);

  // auto-expand tools section on tool pages
  useEffect(() => {
    if (TOOL_LINKS.some(t => pathname.startsWith(t.href))) setToolsOpen(true);
  }, [pathname]);

  const handleNewChat = () => {
    if (pathname === "/chat") {
      window.dispatchEvent(new CustomEvent("junas:new-chat"));
    } else {
      window.location.href = "/chat";
    }
    setActiveConvId("");
    setMobileOpen(false);
  };

  const handleLoadConversation = (id: string) => {
    if (pathname === "/chat") {
      window.dispatchEvent(new CustomEvent("junas:load-conversation", { detail: { id } }));
    } else {
      window.location.href = `/chat?c=${id}`;
    }
    setActiveConvId(id);
    setMobileOpen(false);
  };

  return (
    <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
      <div className="sidebar-header">
        <Link href="/" className="sidebar-brand" onClick={() => setMobileOpen(false)}>Junas</Link>
        <div style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
          <button type="button" className="sidebar-new-chat" onClick={handleNewChat}>+ New</button>
          <button type="button" className="sidebar-toggle" onClick={() => setMobileOpen(v => !v)} aria-label="Toggle navigation">
            {mobileOpen ? "Close" : "Menu"}
          </button>
        </div>
      </div>

      <SessionSidebar
        activeConversationId={activeConvId}
        onLoadConversation={handleLoadConversation}
        onDeletedActive={() => {
          window.dispatchEvent(new CustomEvent("junas:new-chat"));
          setActiveConvId("");
        }}
      />

      <div className="sidebar-tools">
        <button type="button" className="sidebar-tools-toggle" onClick={() => setToolsOpen(v => !v)}>
          <span>Tools</span>
          <span style={{ fontSize: "0.6rem", transition: "transform 0.2s", transform: toolsOpen ? "rotate(180deg)" : "rotate(0)", display: "inline-block" }}>&#9660;</span>
        </button>
        {toolsOpen && (
          <nav className="sidebar-tools-nav">
            {TOOL_LINKS.map(t => (
              <Link key={t.href} href={t.href}
                className={`sidebar-tool-link ${pathname === t.href || pathname.startsWith(`${t.href}/`) ? "active" : ""}`}
                onClick={() => setMobileOpen(false)}>
                {t.label}
              </Link>
            ))}
          </nav>
        )}
      </div>

      <div className="sidebar-footer">
        <Link href="/settings" className="sidebar-settings-link" onClick={() => setMobileOpen(false)}>Settings</Link>
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <button type="button" className="sidebar-notif-btn" onClick={() => setNotifOpen(true)} title="Notifications">
            <span>Logs</span>
            {unreadCount > 0 && <span className="notif-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>}
          </button>
          <ThemeToggle />
        </div>
      </div>
      <NotificationsPanel isOpen={notifOpen} onClose={() => setNotifOpen(false)} />
    </aside>
  );
}
