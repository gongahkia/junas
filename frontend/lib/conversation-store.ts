/**
 * Conversation persistence — localStorage-based save/load/list/delete for chat trees.
 */
import type { NodeMap, TreeMessage } from "./chat-tree";
import {
  createSession,
  deleteSession as deleteSessionApi,
  getSession,
  listSessions,
  renameSession as renameSessionApi,
  saveSession as saveSessionApi,
  type SessionDetail,
} from "./api-client";

export interface ConversationMeta {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}

export interface StoredConversation {
  meta: ConversationMeta;
  nodeMap: NodeMap;
  currentLeafId: string;
}

const META_KEY = "junas_conv_meta";

function metaListKey(): ConversationMeta[] {
  try { return JSON.parse(localStorage.getItem(META_KEY) || "[]"); }
  catch { return []; }
}
function saveMetaList(list: ConversationMeta[]) {
  localStorage.setItem(META_KEY, JSON.stringify(list));
}

export function generateConversationId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function saveConversation(id: string, nodeMap: NodeMap, currentLeafId: string) {
  const messages = Object.values(nodeMap);
  const firstUser = messages.find((m) => m.role === "user");
  const title = firstUser ? firstUser.content.slice(0, 60).replace(/\n/g, " ") : "Untitled";
  const stored: StoredConversation = { meta: { id, title, createdAt: 0, updatedAt: Date.now(), messageCount: messages.length }, nodeMap, currentLeafId };
  // preserve original createdAt
  const existing = loadConversation(id);
  stored.meta.createdAt = existing?.meta.createdAt || Date.now();
  localStorage.setItem(`junas_conv_${id}`, JSON.stringify(stored));
  // update meta list
  const list = metaListKey().filter((m) => m.id !== id);
  list.unshift(stored.meta);
  saveMetaList(list);
  void saveConversationRemote(id, nodeMap, currentLeafId, title).catch(() => undefined);
}

export function loadConversation(id: string): StoredConversation | null {
  try {
    const raw = localStorage.getItem(`junas_conv_${id}`);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch { return null; }
}

export function listConversations(): ConversationMeta[] {
  return metaListKey().sort((a, b) => b.updatedAt - a.updatedAt);
}

export function deleteConversation(id: string) {
  localStorage.removeItem(`junas_conv_${id}`);
  const list = metaListKey().filter((m) => m.id !== id);
  saveMetaList(list);
}

function fromSessionDetail(detail: SessionDetail): StoredConversation {
  return {
    meta: {
      id: detail.id,
      title: detail.title,
      createdAt: Date.parse(detail.created_at),
      updatedAt: Date.parse(detail.updated_at),
      messageCount: detail.message_count,
    },
    nodeMap: detail.node_map as NodeMap,
    currentLeafId: detail.current_leaf_id,
  };
}

function cacheRemoteConversation(detail: SessionDetail): StoredConversation {
  const stored = fromSessionDetail(detail);
  localStorage.setItem(`junas_conv_${stored.meta.id}`, JSON.stringify(stored));
  const list = metaListKey().filter((m) => m.id !== stored.meta.id);
  list.unshift(stored.meta);
  saveMetaList(list);
  return stored;
}

export async function saveConversationRemote(id: string, nodeMap: NodeMap, currentLeafId: string, title?: string): Promise<StoredConversation | null> {
  const payload = { id, title, node_map: nodeMap, current_leaf_id: currentLeafId };
  const existing = await getSession(id);
  const response = existing ? await saveSessionApi(id, payload) : await createSession(payload);
  if (response.error) return null;
  return cacheRemoteConversation(response);
}

export async function loadConversationRemote(id: string): Promise<StoredConversation | null> {
  const detail = await getSession(id);
  return detail ? cacheRemoteConversation(detail) : null;
}

export async function listConversationsRemote(): Promise<ConversationMeta[]> {
  const sessions = await listSessions();
  if (sessions.length === 0) return [];
  const metas = sessions.map((session) => ({
    id: session.id,
    title: session.title,
    createdAt: Date.parse(session.created_at),
    updatedAt: Date.parse(session.updated_at),
    messageCount: session.message_count,
  }));
  saveMetaList(metas);
  return metas;
}

export async function renameConversationRemote(id: string, title: string): Promise<ConversationMeta | null> {
  const response = await renameSessionApi(id, title);
  if (response.error) return null;
  const stored = cacheRemoteConversation(response);
  return stored.meta;
}

export async function deleteConversationRemote(id: string): Promise<boolean> {
  const response = await deleteSessionApi(id);
  return !response.error;
}
