import { mkdir, readTextFile, writeTextFile, readDir, remove, exists } from '@tauri-apps/plugin-fs';
import { appDataDir } from '@tauri-apps/api/path';
let basePath: string | null = null;
async function getBasePath(): Promise<string> {
  if (!basePath) basePath = await appDataDir();
  return basePath;
}
async function ensureDir(path: string) {
  if (!(await exists(path))) await mkdir(path, { recursive: true });
}
async function readJson<T>(path: string, fallback: T): Promise<T> {
  try {
    if (!(await exists(path))) return fallback;
    const text = await readTextFile(path);
    return JSON.parse(text) as T;
  } catch {
    return fallback;
  }
}
async function writeJson(path: string, data: unknown) {
  await writeTextFile(path, JSON.stringify(data, null, 2));
}
// task 35: save conversation
export async function saveConversation(id: string, data: unknown) {
  const base = await getBasePath();
  const dir = `${base}/conversations`;
  await ensureDir(dir);
  await writeJson(`${dir}/${id}.json`, data);
}
// task 36: load conversation
export async function loadConversation(id: string): Promise<unknown | null> {
  const base = await getBasePath();
  return readJson(`${base}/conversations/${id}.json`, null);
}
// task 37: list conversations
export async function listConversations(): Promise<
  { id: string; name: string; updatedAt: string }[]
> {
  const base = await getBasePath();
  const dir = `${base}/conversations`;
  await ensureDir(dir);
  try {
    const entries = await readDir(dir);
    const results: { id: string; name: string; updatedAt: string }[] = [];
    for (const entry of entries) {
      if (entry.name?.endsWith('.json')) {
        const id = entry.name.replace('.json', '');
        const data = await readJson<any>(`${dir}/${entry.name}`, null);
        if (data)
          results.push({
            id,
            name: data.title || data.name || id,
            updatedAt: data.updatedAt || '',
          });
      }
    }
    return results;
  } catch {
    return [];
  }
}
// task 38: delete conversation
export async function deleteConversation(id: string) {
  const base = await getBasePath();
  const path = `${base}/conversations/${id}.json`;
  if (await exists(path)) await remove(path);
}
// task 39: save settings
export async function saveSettings(settings: unknown) {
  const base = await getBasePath();
  await ensureDir(base);
  await writeJson(`${base}/settings.json`, settings);
}
// task 40: load settings
export async function loadSettings<T>(defaults: T): Promise<T> {
  const base = await getBasePath();
  return readJson<T>(`${base}/settings.json`, defaults);
}
// task 41: profiles
export async function saveProfiles(profiles: unknown) {
  const base = await getBasePath();
  await ensureDir(base);
  await writeJson(`${base}/profiles.json`, profiles);
}
export async function loadProfiles<T>(defaults: T): Promise<T> {
  const base = await getBasePath();
  return readJson<T>(`${base}/profiles.json`, defaults);
}
// task 42: snippets
export async function saveSnippets(snippets: unknown) {
  const base = await getBasePath();
  await ensureDir(base);
  await writeJson(`${base}/snippets.json`, snippets);
}
export async function loadSnippets<T>(defaults: T): Promise<T> {
  const base = await getBasePath();
  return readJson<T>(`${base}/snippets.json`, defaults);
}

// local observability errors
export async function saveErrorEvents(events: unknown) {
  const base = await getBasePath();
  await ensureDir(base);
  await writeJson(`${base}/observability-errors.json`, events);
}

export async function loadErrorEvents<T>(defaults: T): Promise<T> {
  const base = await getBasePath();
  return readJson<T>(`${base}/observability-errors.json`, defaults);
}
