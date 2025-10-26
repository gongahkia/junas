import DOMPurify from 'isomorphic-dompurify';

/**
 * Sanitization utilities for user input
 */

/**
 * Sanitize HTML content to prevent XSS attacks
 */
export function sanitizeHTML(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'code', 'pre'],
    ALLOWED_ATTR: ['href', 'title'],
    ALLOW_DATA_ATTR: false,
  });
}

/**
 * Sanitize plain text by removing potentially dangerous characters
 */
export function sanitizePlainText(text: string): string {
  // Remove null bytes
  let sanitized = text.replace(/\0/g, '');

  // Remove control characters except newlines and tabs
  sanitized = sanitized.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');

  // Trim excessive whitespace
  sanitized = sanitized.replace(/\s+/g, ' ').trim();

  return sanitized;
}

/**
 * Sanitize message content for chat
 */
export function sanitizeMessageContent(content: string, allowHTML: boolean = false): string {
  if (allowHTML) {
    return sanitizeHTML(content);
  }
  return sanitizePlainText(content);
}

/**
 * Sanitize filename to prevent path traversal attacks
 */
export function sanitizeFilename(filename: string): string {
  // Remove any path components
  let sanitized = filename.replace(/^.*[\\\/]/, '');

  // Remove potentially dangerous characters
  sanitized = sanitized.replace(/[<>:"|?*\x00-\x1F]/g, '');

  // Limit length
  if (sanitized.length > 255) {
    const ext = sanitized.split('.').pop() || '';
    const nameWithoutExt = sanitized.slice(0, sanitized.lastIndexOf('.'));
    sanitized = nameWithoutExt.slice(0, 255 - ext.length - 1) + '.' + ext;
  }

  return sanitized || 'unnamed';
}

/**
 * Sanitize search query to prevent injection attacks
 */
export function sanitizeSearchQuery(query: string): string {
  // Remove special characters that could be used for injection
  let sanitized = query.trim();

  // Remove multiple spaces
  sanitized = sanitized.replace(/\s+/g, ' ');

  // Remove potentially dangerous special characters
  sanitized = sanitized.replace(/[<>{}[\]\\|;]/g, '');

  return sanitized;
}

/**
 * Validate and sanitize URL
 */
export function sanitizeURL(url: string): string | null {
  try {
    const parsed = new URL(url);

    // Only allow http and https
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null;
    }

    return parsed.toString();
  } catch {
    return null;
  }
}
