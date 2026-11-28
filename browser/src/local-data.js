import { MODEL, MODEL_IDS } from "./contract.js";
export const DEFAULT_SETTINGS = { model: MODEL, threshold: 0.85, pii: true, mnpi: true };
export function validateSettings(value) {
  if (!value || !MODEL_IDS.includes(value.model) || !Number.isFinite(value.threshold) || value.threshold < 0 || value.threshold > 1 || typeof value.pii !== "boolean" || typeof value.mnpi !== "boolean") throw Error("Invalid redaction settings.");
  return { model: value.model, threshold: value.threshold, pii: value.pii, mnpi: value.mnpi };
}
let opening;
function database() {
  opening ??= new Promise((resolve, reject) => {
    const request = indexedDB.open("junas-local", 1);
    request.onupgradeneeded = () => { request.result.createObjectStore("settings"); request.result.createObjectStore("history", { keyPath: "id" }); };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => { opening = undefined; reject(Error("Local storage unavailable.")); };
  });
  return opening;
}
async function transaction(store, write, action) {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, write ? "readwrite" : "readonly");
    let value;
    const request = action(tx.objectStore(store));
    if (request) request.onsuccess = () => { value = request.result; };
    tx.oncomplete = () => resolve(value);
    tx.onerror = tx.onabort = () => reject(Error("Local storage operation failed."));
  });
}
export async function settings() { return validateSettings(await transaction("settings", false, s => s.get("current")) ?? DEFAULT_SETTINGS); }
export async function saveSettings(value) { const next = validateSettings(value); await transaction("settings", true, s => s.put(next, "current")); return next; }
export async function history() { return (await transaction("history", false, s => s.getAll())).sort((a, b) => b.created - a.created); }
export async function saveHistory(record) {
  const db = await database();
  await new Promise((resolve, reject) => {
    const tx = db.transaction("history", "readwrite"), store = tx.objectStore("history");
    store.put(record);
    const all = store.getAll();
    all.onsuccess = () => all.result.sort((a, b) => b.created - a.created).slice(20).forEach(row => store.delete(row.id));
    tx.oncomplete = resolve; tx.onerror = tx.onabort = () => reject(Error("History could not be saved."));
  });
}
export async function deleteHistory(id) { await transaction("history", true, s => id ? s.delete(id) : s.clear()); }
