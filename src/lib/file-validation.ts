import { fileTypeFromBuffer } from 'file-type';

/**
 * File validation utilities using magic number checking
 */

/**
 * Allowed file types with their magic numbers
 */
export const ALLOWED_MIME_TYPES = {
  // Documents
  'application/pdf': { ext: 'pdf', magic: [0x25, 0x50, 0x44, 0x46] }, // %PDF
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': { ext: 'docx', magic: [0x50, 0x4B, 0x03, 0x04] }, // PK (ZIP)

  // Images
  'image/jpeg': { ext: 'jpg', magic: [0xFF, 0xD8, 0xFF] },
  'image/png': { ext: 'png', magic: [0x89, 0x50, 0x4E, 0x47] },
  'image/gif': { ext: 'gif', magic: [0x47, 0x49, 0x46, 0x38] },
  'image/bmp': { ext: 'bmp', magic: [0x42, 0x4D] },
  'image/webp': { ext: 'webp', magic: [0x52, 0x49, 0x46, 0x46] },
} as const;

export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

/**
 * Validate file based on magic numbers (actual file content)
 */
export async function validateFileType(buffer: ArrayBuffer): Promise<{
  valid: boolean;
  mimeType?: string;
  ext?: string;
  error?: string;
}> {
  try {
    const uint8Array = new Uint8Array(buffer);

    // Use file-type library to detect actual file type
    const fileType = await fileTypeFromBuffer(uint8Array);

    if (!fileType) {
      return {
        valid: false,
        error: 'Could not determine file type',
      };
    }

    // Check if the detected type is in our allowed list
    if (!(fileType.mime in ALLOWED_MIME_TYPES)) {
      return {
        valid: false,
        error: `File type ${fileType.mime} is not allowed`,
      };
    }

    return {
      valid: true,
      mimeType: fileType.mime,
      ext: fileType.ext,
    };
  } catch (error) {
    return {
      valid: false,
      error: 'File validation failed',
    };
  }
}

/**
 * Validate file size
 */
export function validateFileSize(size: number): { valid: boolean; error?: string } {
  if (size <= 0) {
    return {
      valid: false,
      error: 'File is empty',
    };
  }

  if (size > MAX_FILE_SIZE) {
    return {
      valid: false,
      error: `File size (${(size / 1024 / 1024).toFixed(2)}MB) exceeds maximum allowed size (${MAX_FILE_SIZE / 1024 / 1024}MB)`,
    };
  }

  return { valid: true };
}

/**
 * Comprehensive file validation
 */
export async function validateFile(file: {
  buffer: ArrayBuffer;
  name: string;
  size: number;
}): Promise<{
  valid: boolean;
  mimeType?: string;
  ext?: string;
  error?: string;
}> {
  // Validate size first (cheaper operation)
  const sizeValidation = validateFileSize(file.size);
  if (!sizeValidation.valid) {
    return sizeValidation;
  }

  // Validate file type via magic numbers
  const typeValidation = await validateFileType(file.buffer);
  if (!typeValidation.valid) {
    return typeValidation;
  }

  return {
    valid: true,
    mimeType: typeValidation.mimeType,
    ext: typeValidation.ext,
  };
}

/**
 * Check if filename extension matches detected file type
 */
export function validateFileExtension(filename: string, detectedExt: string): boolean {
  const fileExt = filename.split('.').pop()?.toLowerCase();
  return fileExt === detectedExt;
}
