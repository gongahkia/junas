/**
 * Migration utility for legacy browser key storage.
 * Moves old bundled key payloads into per-provider keys used by the current runtime adapters.
 */
import { isTauriRuntime } from '@/lib/runtime';

const WEB_KEY_PREFIX = 'junas_web_api_key_';

export async function migrateApiKeysToSession(): Promise<boolean> {
  try {
    // Desktop app uses OS keychain via Tauri commands.
    if (isTauriRuntime()) {
      localStorage.setItem('junas_keys_migrated', 'true');
      return true;
    }

    // Browser mode migration: move legacy key bundle into per-provider browser keys.
    const migrated = localStorage.getItem('junas_keys_migrated');
    if (migrated === 'true') {
      return true;
    }

    const oldKeysStr = localStorage.getItem('junas_api_keys');
    if (!oldKeysStr) {
      localStorage.setItem('junas_keys_migrated', 'true');
      return true;
    }

    try {
      const oldKeys = JSON.parse(oldKeysStr) as Record<string, unknown>;
      for (const [provider, key] of Object.entries(oldKeys)) {
        if (typeof key === 'string' && key.trim().length > 0) {
          localStorage.setItem(`${WEB_KEY_PREFIX}${provider}`, key.trim());
        }
      }
      localStorage.removeItem('junas_api_keys');
      localStorage.setItem('junas_keys_migrated', 'true');
      return true;
    } catch (error) {
      console.error('Error parsing old API keys:', error);
      return false;
    }
  } catch (error) {
    console.error('Migration error:', error);
    return false;
  }
}

/**
 * Check if migration is needed
 */
export function needsMigration(): boolean {
  if (isTauriRuntime()) {
    return false;
  }

  const migrated = localStorage.getItem('junas_keys_migrated');
  const hasOldKeys = localStorage.getItem('junas_api_keys');
  return migrated !== 'true' && !!hasOldKeys;
}
