/**
 * Migration utility to transfer API keys from localStorage to session storage
 * This ensures users don't lose their configured keys after the security upgrade
 */

export async function migrateApiKeysToSession(): Promise<boolean> {
  try {
    // Check if already migrated
    const migrated = localStorage.getItem('junas_keys_migrated');
    if (migrated === 'true') {
      return true;
    }

    // Try to get old API keys from localStorage
    const oldKeysStr = localStorage.getItem('junas_api_keys');
    if (!oldKeysStr) {
      // No old keys to migrate
      localStorage.setItem('junas_keys_migrated', 'true');
      return true;
    }

    try {
      const oldKeys = JSON.parse(oldKeysStr);

      // Send keys to session storage
      const response = await fetch('/api/auth/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(oldKeys),
      });

      if (response.ok) {
        // Migration successful - remove old keys and mark as migrated
        localStorage.removeItem('junas_api_keys');
        localStorage.setItem('junas_keys_migrated', 'true');
        console.log('Successfully migrated API keys to secure session storage');
        return true;
      } else {
        console.error('Failed to migrate API keys to session');
        return false;
      }
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
  const migrated = localStorage.getItem('junas_keys_migrated');
  const hasOldKeys = localStorage.getItem('junas_api_keys');
  return migrated !== 'true' && !!hasOldKeys;
}
