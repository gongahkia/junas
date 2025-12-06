/**
 * Utility functions for processing and handling file attachments
 */

export interface ProcessedFileContent {
  text: string;
  metadata: {
    fileName: string;
    fileType: string;
    fileSize: number;
    processed: boolean;
    extractedText?: string;
    error?: string;
  };
}

/**
 * Process file content based on file type
 */
export async function processFileContent(
  file: File,
  content: string
): Promise<ProcessedFileContent> {
  const metadata = {
    fileName: file.name,
    fileType: file.type,
    fileSize: file.size,
    processed: true,
  };

  try {
    // Handle different file types
    if (file.type.startsWith('image/')) {
      return processImage(file, content, metadata);
    } else if (file.type === 'application/pdf') {
      return processPDF(file, content, metadata);
    } else if (
      file.type.startsWith('text/') ||
      file.type === 'application/json' ||
      file.name.endsWith('.txt') ||
      file.name.endsWith('.md')
    ) {
      return processTextFile(content, metadata);
    } else if (
      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
      file.name.endsWith('.docx')
    ) {
      return processWordDocument(file, content, metadata);
    } else {
      // Unsupported file type
      return {
        text: `[Unsupported file type: ${file.type}]`,
        metadata: {
          ...metadata,
          processed: false,
          error: 'Unsupported file type',
        },
      };
    }
  } catch (error) {
    console.error('Error processing file:', error);
    return {
      text: `[Error processing file: ${file.name}]`,
      metadata: {
        ...metadata,
        processed: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      },
    };
  }
}

/**
 * Process image files
 */
async function processImage(
  file: File,
  dataUrl: string,
  metadata: any
): Promise<ProcessedFileContent> {
  // For now, just indicate an image is attached
  // In the future, this could use OCR or vision APIs
  return {
    text: `[Image: ${file.name}]\nNote: Image content analysis not yet implemented. Please describe the image in your question.`,
    metadata: {
      ...metadata,
      extractedText: 'Image file - manual description required',
    },
  };
}

/**
 * Process PDF files
 */
async function processPDF(
  file: File,
  content: string,
  metadata: any
): Promise<ProcessedFileContent> {
  // PDF text extraction would require a library like pdf.js
  // For now, just indicate a PDF is attached
  return {
    text: `[PDF Document: ${file.name}]\nNote: PDF text extraction not yet implemented. Please summarize the key points.`,
    metadata: {
      ...metadata,
      extractedText: 'PDF file - manual summary required',
    },
  };
}

/**
 * Process plain text files
 */
async function processTextFile(
  content: string,
  metadata: any
): Promise<ProcessedFileContent> {
  // Clean and format the text
  const cleanedText = content
    .replace(/\r\n/g, '\n') // Normalize line endings
    .replace(/\n{3,}/g, '\n\n') // Remove excessive newlines
    .trim();

  return {
    text: cleanedText,
    metadata: {
      ...metadata,
      extractedText: `${cleanedText.length} characters extracted`,
    },
  };
}

/**
 * Process Word documents (.docx)
 */
async function processWordDocument(
  file: File,
  content: string,
  metadata: any
): Promise<ProcessedFileContent> {
  // DOCX parsing would require a library like mammoth.js
  // For now, just indicate a Word doc is attached
  return {
    text: `[Word Document: ${file.name}]\nNote: Word document text extraction not yet implemented. Please summarize the key points.`,
    metadata: {
      ...metadata,
      extractedText: 'Word document - manual summary required',
    },
  };
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Validate file before upload
 */
export function validateFile(file: File): {
  valid: boolean;
  error?: string;
} {
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
  const ALLOWED_TYPES = [
    'text/plain',
    'application/pdf',
    'application/json',
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/gif',
    'image/webp',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  ];

  const ALLOWED_EXTENSIONS = [
    '.txt',
    '.pdf',
    '.json',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.webp',
    '.docx',
    '.md',
  ];

  if (file.size > MAX_FILE_SIZE) {
    return {
      valid: false,
      error: `File size exceeds 10MB limit (${formatFileSize(file.size)})`,
    };
  }

  const hasValidType = ALLOWED_TYPES.includes(file.type);
  const hasValidExtension = ALLOWED_EXTENSIONS.some((ext) =>
    file.name.toLowerCase().endsWith(ext)
  );

  if (!hasValidType && !hasValidExtension) {
    return {
      valid: false,
      error: `Unsupported file type: ${file.type || 'unknown'}`,
    };
  }

  return { valid: true };
}

/**
 * Extract text content for context
 */
export function extractTextForContext(
  content: string,
  maxLength: number = 5000
): string {
  if (content.length <= maxLength) {
    return content;
  }

  // Take first part and last part to maintain context
  const halfLength = Math.floor(maxLength / 2);
  const start = content.slice(0, halfLength);
  const end = content.slice(-halfLength);

  return `${start}\n\n[... ${content.length - maxLength} characters omitted ...]\n\n${end}`;
}
