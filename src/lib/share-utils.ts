import LZString from 'lz-string';
import { Message } from '@/types/chat';

/**
 * Compresses the chat messages into a URL-safe string.
 */
export function compressChat(messages: Message[]): string {
  try {
    const json = JSON.stringify(messages);
    return LZString.compressToEncodedURIComponent(json);
  } catch (error) {
    console.error('Failed to compress chat:', error);
    return '';
  }
}

/**
 * Decompresses a URL-safe string back into chat messages.
 */
export function decompressChat(compressed: string): Message[] | null {
  try {
    const json = LZString.decompressFromEncodedURIComponent(compressed);
    if (!json) return null;
    
    const messages = JSON.parse(json);
    
    // Basic validation to ensure it's an array
    if (!Array.isArray(messages)) return null;
    
    return messages;
  } catch (error) {
    console.error('Failed to decompress chat:', error);
    return null;
  }
}
