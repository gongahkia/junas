import { admitText } from "./contract.js";

const PREFIX = "selection:";
export async function queueSelection(api, text, now = Date.now(), id = crypto.randomUUID()) {
  admitText(text);
  const entries = await api.storage.session.get(null);
  const selections = Object.entries(entries).filter(([key]) => key.startsWith(PREFIX));
  // bound pending selections and discard expired entries on each capture.
  const stale = selections.filter(([, entry]) => !Number.isFinite(entry?.created) || now - entry.created > 300_000).map(([key]) => key);
  const live = selections.filter(([key]) => !stale.includes(key)).sort((a, b) => a[1].created - b[1].created);
  await api.storage.session.remove([...stale, ...live.slice(0, Math.max(0, live.length - 15)).map(([key]) => key)]);
  await api.storage.session.set({ [PREFIX + id]: { text, created: now } });
  await api.tabs.create({ url: api.runtime.getURL(`process.html?selection=${encodeURIComponent(id)}`) });
}

export async function consumeSelection(api, id, now = Date.now()) {
  if (!/^[a-zA-Z0-9-]{1,80}$/.test(id)) throw Error("Invalid selection reference.");
  const key = PREFIX + id;
  const entry = (await api.storage.session.get(key))[key];
  await api.storage.session.remove(key);
  if (!entry || !Number.isFinite(entry.created) || now - entry.created > 300_000) throw Error("Selection expired. Highlight the text again.");
  return admitText(entry.text);
}
