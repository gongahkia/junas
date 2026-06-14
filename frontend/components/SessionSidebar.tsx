"use client";

import { useEffect, useState } from "react";
import {
  deleteConversation,
  deleteConversationRemote,
  listConversations,
  listConversationsRemote,
  renameConversationRemote,
  type ConversationMeta,
} from "../lib/conversation-store";

type Props = {
  activeConversationId: string;
  onLoadConversation: (id: string) => void;
  onDeletedActive: () => void;
};

function formatDate(ts: number): string {
  const now = Date.now();
  const diff = now - ts;
  if (diff < 86400000) return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date(ts));
  if (diff < 604800000) return new Intl.DateTimeFormat("en-US", { weekday: "short" }).format(new Date(ts));
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(ts));
}

export default function SessionSidebar({ activeConversationId, onLoadConversation, onDeletedActive }: Props) {
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [open, setOpen] = useState(true);

  const refresh = () => {
    setConversations(listConversations());
    void listConversationsRemote().then((remote) => {
      if (remote.length > 0) setConversations(remote);
    }).catch(() => undefined);
  };

  useEffect(() => {
    refresh();
    window.addEventListener("junas:conversations-updated", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("junas:conversations-updated", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  const rename = async (conversation: ConversationMeta, event: React.MouseEvent) => {
    event.stopPropagation();
    const title = window.prompt("Rename session", conversation.title)?.trim();
    if (!title) return;
    const renamed = await renameConversationRemote(conversation.id, title);
    if (renamed) refresh();
  };

  const remove = (conversation: ConversationMeta, event: React.MouseEvent) => {
    event.stopPropagation();
    deleteConversation(conversation.id);
    void deleteConversationRemote(conversation.id).finally(refresh);
    if (activeConversationId === conversation.id) onDeletedActive();
  };

  return (
    <>
      <button type="button" className="sidebar-tools-toggle" onClick={() => setOpen((value) => !value)}>
        <span>Recent</span>
        <span style={{ fontSize: "0.6rem", transition: "transform 0.2s", transform: open ? "rotate(180deg)" : "rotate(0)", display: "inline-block" }}>&#9660;</span>
      </button>
      {open && (
        <div className="sidebar-conversations">
          {conversations.length === 0 && (
            <div style={{ padding: "0.75rem 0.6rem", color: "#A8A29E", fontSize: "0.78rem" }}>No conversations yet</div>
          )}
          {conversations.slice(0, 50).map((conversation) => (
            <div key={conversation.id} className={`sidebar-conv-item ${activeConversationId === conversation.id ? "active" : ""}`} onClick={() => onLoadConversation(conversation.id)}>
              <span className="sidebar-conv-title">{conversation.title}</span>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.25rem" }}>
                <span className="sidebar-conv-meta">{conversation.messageCount} msgs · {formatDate(conversation.updatedAt)}</span>
                <span style={{ display: "inline-flex", gap: "0.2rem" }}>
                  <button type="button" className="sidebar-conv-delete" onClick={(event) => rename(conversation, event)} title="Rename">R</button>
                  <button type="button" className="sidebar-conv-delete" onClick={(event) => remove(conversation, event)} title="Delete">&times;</button>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
