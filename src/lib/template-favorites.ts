/**
 * Template favorites management
 * Allows users to bookmark frequently used templates
 */

const FAVORITES_KEY = 'junas_template_favorites';

/**
 * Get all favorited template IDs
 */
export function getFavoriteTemplates(): string[] {
  try {
    if (typeof window === 'undefined') return [];
    const stored = localStorage.getItem(FAVORITES_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch (error) {
    console.error('Error loading favorites:', error);
    return [];
  }
}

/**
 * Add a template to favorites
 */
export function addToFavorites(templateId: string): void {
  const favorites = getFavoriteTemplates();
  if (!favorites.includes(templateId)) {
    favorites.push(templateId);
    try {
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
    } catch (error) {
      console.error('Error saving favorite:', error);
    }
  }
}

/**
 * Remove a template from favorites
 */
export function removeFromFavorites(templateId: string): void {
  const favorites = getFavoriteTemplates();
  const filtered = favorites.filter(id => id !== templateId);
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(filtered));
  } catch (error) {
    console.error('Error removing favorite:', error);
  }
}

/**
 * Check if a template is favorited
 */
export function isFavorite(templateId: string): boolean {
  const favorites = getFavoriteTemplates();
  return favorites.includes(templateId);
}

/**
 * Toggle favorite status
 */
export function toggleFavorite(templateId: string): boolean {
  if (isFavorite(templateId)) {
    removeFromFavorites(templateId);
    return false;
  } else {
    addToFavorites(templateId);
    return true;
  }
}

/**
 * Clear all favorites
 */
export function clearFavorites(): void {
  try {
    localStorage.removeItem(FAVORITES_KEY);
  } catch (error) {
    console.error('Error clearing favorites:', error);
  }
}
