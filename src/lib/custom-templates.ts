import { LegalTemplate } from './templates';

/**
 * Custom template management for user-created templates
 * Stored in localStorage
 */

const CUSTOM_TEMPLATES_KEY = 'junas_custom_templates';

export interface CustomTemplate extends LegalTemplate {
  createdAt: string;
  updatedAt: string;
  isCustom: true;
}

/**
 * Get all custom templates from localStorage
 */
export function getCustomTemplates(): CustomTemplate[] {
  try {
    if (typeof window === 'undefined') return [];
    const stored = localStorage.getItem(CUSTOM_TEMPLATES_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch (error) {
    console.error('Error loading custom templates:', error);
    return [];
  }
}

/**
 * Save a new custom template
 */
export function saveCustomTemplate(
  template: Omit<LegalTemplate, 'id'>
): CustomTemplate {
  const customTemplate: CustomTemplate = {
    ...template,
    id: `custom-${Date.now()}-${Math.random().toString(36).substring(7)}`,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    isCustom: true,
  };

  const templates = getCustomTemplates();
  templates.push(customTemplate);

  try {
    localStorage.setItem(CUSTOM_TEMPLATES_KEY, JSON.stringify(templates));
  } catch (error) {
    console.error('Error saving custom template:', error);
    throw new Error('Failed to save custom template');
  }

  return customTemplate;
}

/**
 * Update an existing custom template
 */
export function updateCustomTemplate(
  id: string,
  updates: Partial<Omit<LegalTemplate, 'id'>>
): CustomTemplate | null {
  const templates = getCustomTemplates();
  const index = templates.findIndex((t) => t.id === id);

  if (index === -1) {
    return null;
  }

  templates[index] = {
    ...templates[index],
    ...updates,
    updatedAt: new Date().toISOString(),
  };

  try {
    localStorage.setItem(CUSTOM_TEMPLATES_KEY, JSON.stringify(templates));
  } catch (error) {
    console.error('Error updating custom template:', error);
    throw new Error('Failed to update custom template');
  }

  return templates[index];
}

/**
 * Delete a custom template
 */
export function deleteCustomTemplate(id: string): boolean {
  const templates = getCustomTemplates();
  const filtered = templates.filter((t) => t.id !== id);

  if (filtered.length === templates.length) {
    return false; // Template not found
  }

  try {
    localStorage.setItem(CUSTOM_TEMPLATES_KEY, JSON.stringify(filtered));
    return true;
  } catch (error) {
    console.error('Error deleting custom template:', error);
    throw new Error('Failed to delete custom template');
  }
}

/**
 * Create a custom template from an existing template
 */
export function cloneTemplate(
  baseTemplate: LegalTemplate,
  customizations?: Partial<Omit<LegalTemplate, 'id'>>
): CustomTemplate {
  return saveCustomTemplate({
    ...baseTemplate,
    ...customizations,
    name: customizations?.name || `${baseTemplate.name} (Custom)`,
  });
}

/**
 * Export custom templates to JSON
 */
export function exportCustomTemplates(): string {
  const templates = getCustomTemplates();
  return JSON.stringify(templates, null, 2);
}

/**
 * Import custom templates from JSON
 */
export function importCustomTemplates(jsonData: string): number {
  try {
    const imported: CustomTemplate[] = JSON.parse(jsonData);

    if (!Array.isArray(imported)) {
      throw new Error('Invalid format: expected array of templates');
    }

    const existing = getCustomTemplates();
    const merged = [...existing, ...imported];

    localStorage.setItem(CUSTOM_TEMPLATES_KEY, JSON.stringify(merged));
    return imported.length;
  } catch (error) {
    console.error('Error importing custom templates:', error);
    throw new Error('Failed to import custom templates');
  }
}
