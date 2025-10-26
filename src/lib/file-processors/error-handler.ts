/**
 * Error handling utilities for file processing operations
 */

export class FileProcessingError extends Error {
  constructor(
    message: string,
    public code: string,
    public fileType?: string,
    public recoverable: boolean = false
  ) {
    super(message);
    this.name = 'FileProcessingError';
  }
}

export class PDFProcessingError extends FileProcessingError {
  constructor(message: string, recoverable: boolean = false) {
    super(message, 'PDF_ERROR', 'pdf', recoverable);
    this.name = 'PDFProcessingError';
  }
}

export class DOCXProcessingError extends FileProcessingError {
  constructor(message: string, recoverable: boolean = false) {
    super(message, 'DOCX_ERROR', 'docx', recoverable);
    this.name = 'DOCXProcessingError';
  }
}

export class OCRProcessingError extends FileProcessingError {
  constructor(message: string, recoverable: boolean = false) {
    super(message, 'OCR_ERROR', 'image', recoverable);
    this.name = 'OCRProcessingError';
  }
}

export class FileSizeError extends FileProcessingError {
  constructor(size: number, maxSize: number) {
    super(
      `File size (${formatBytes(size)}) exceeds maximum allowed size (${formatBytes(maxSize)})`,
      'FILE_TOO_LARGE',
      undefined,
      false
    );
    this.name = 'FileSizeError';
  }
}

export class FileTypeError extends FileProcessingError {
  constructor(detectedType: string, expectedTypes: string[]) {
    super(
      `Invalid file type: ${detectedType}. Expected one of: ${expectedTypes.join(', ')}`,
      'INVALID_FILE_TYPE',
      undefined,
      false
    );
    this.name = 'FileTypeError';
  }
}

export class CorruptedFileError extends FileProcessingError {
  constructor(fileType: string) {
    super(
      `File appears to be corrupted or malformed (${fileType})`,
      'CORRUPTED_FILE',
      fileType,
      false
    );
    this.name = 'CorruptedFileError';
  }
}

/**
 * Error handler for file processing operations
 */
export class FileErrorHandler {
  /**
   * Handle and normalize errors from file processing
   */
  static handle(error: any, fileType?: string): FileProcessingError {
    // Already a FileProcessingError
    if (error instanceof FileProcessingError) {
      return error;
    }

    // PDF-specific errors
    if (error.message?.includes('PDF') || error.message?.includes('pdf')) {
      return new PDFProcessingError(
        this.sanitizeErrorMessage(error.message),
        this.isRecoverableError(error)
      );
    }

    // DOCX-specific errors
    if (error.message?.includes('DOCX') || error.message?.includes('docx') ||
        error.message?.includes('mammoth')) {
      return new DOCXProcessingError(
        this.sanitizeErrorMessage(error.message),
        this.isRecoverableError(error)
      );
    }

    // OCR-specific errors
    if (error.message?.includes('Tesseract') || error.message?.includes('OCR')) {
      return new OCRProcessingError(
        this.sanitizeErrorMessage(error.message),
        this.isRecoverableError(error)
      );
    }

    // File size errors
    if (error.code === 'FILE_TOO_LARGE' || error.message?.includes('too large')) {
      return new FileSizeError(0, 0); // Size info lost, but error type preserved
    }

    // Corrupted file errors
    if (error.message?.includes('corrupt') || error.message?.includes('malformed') ||
        error.message?.includes('invalid format')) {
      return new CorruptedFileError(fileType || 'unknown');
    }

    // Generic file processing error
    return new FileProcessingError(
      this.sanitizeErrorMessage(error.message || 'Unknown file processing error'),
      'UNKNOWN_ERROR',
      fileType,
      this.isRecoverableError(error)
    );
  }

  /**
   * Check if error is recoverable
   */
  static isRecoverableError(error: any): boolean {
    if (error instanceof FileProcessingError) {
      return error.recoverable;
    }

    // Network errors are recoverable
    if (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT') {
      return true;
    }

    // Memory errors might be recoverable with smaller chunks
    if (error.code === 'ERR_OUT_OF_MEMORY') {
      return true;
    }

    // Most other errors are not recoverable
    return false;
  }

  /**
   * Sanitize error messages to remove sensitive information
   */
  static sanitizeErrorMessage(message: string): string {
    return message
      // Remove file paths
      .replace(/[A-Z]:\\[^\s]*/g, '[REDACTED_PATH]')
      .replace(/\/[^\s]*/g, '[REDACTED_PATH]')
      // Remove URLs
      .replace(/https?:\/\/[^\s]*/g, '[REDACTED_URL]')
      // Truncate very long messages
      .slice(0, 500);
  }

  /**
   * Get user-friendly error message
   */
  static getUserMessage(error: FileProcessingError): string {
    switch (error.code) {
      case 'PDF_ERROR':
        return 'Unable to process PDF file. The file may be password-protected, corrupted, or in an unsupported format.';

      case 'DOCX_ERROR':
        return 'Unable to process Word document. The file may be corrupted or in an older format (try converting to .docx).';

      case 'OCR_ERROR':
        return 'Unable to extract text from image. The image may be too low quality or contain no readable text.';

      case 'FILE_TOO_LARGE':
        return 'File is too large. Please try a smaller file or compress the content.';

      case 'INVALID_FILE_TYPE':
        return 'File type not supported. Please upload a PDF, DOCX, or image file.';

      case 'CORRUPTED_FILE':
        return 'File appears to be corrupted or malformed. Please try re-saving or re-exporting the file.';

      default:
        return 'An error occurred while processing the file. Please try again or contact support.';
    }
  }

  /**
   * Get recovery suggestions
   */
  static getRecoverySuggestions(error: FileProcessingError): string[] {
    const suggestions: string[] = [];

    switch (error.code) {
      case 'PDF_ERROR':
        suggestions.push('Try removing password protection from the PDF');
        suggestions.push('Re-save the PDF using a different PDF viewer');
        suggestions.push('Ensure the PDF is not a scanned image (or enable OCR)');
        break;

      case 'DOCX_ERROR':
        suggestions.push('Convert the document to .docx format');
        suggestions.push('Try opening and re-saving in Microsoft Word or Google Docs');
        suggestions.push('Check if the file has any macros or embedded content');
        break;

      case 'OCR_ERROR':
        suggestions.push('Use a higher quality scan or image');
        suggestions.push('Ensure the text is clearly visible and not blurry');
        suggestions.push('Try a different image format (PNG recommended)');
        break;

      case 'FILE_TOO_LARGE':
        suggestions.push('Compress the file using a compression tool');
        suggestions.push('Remove unnecessary images or content');
        suggestions.push('Split into multiple smaller files');
        break;

      case 'CORRUPTED_FILE':
        suggestions.push('Try re-downloading or re-exporting the file');
        suggestions.push('Open and save in the native application');
        suggestions.push('Use file repair tools if available');
        break;
    }

    return suggestions;
  }
}

/**
 * Format bytes to human-readable string
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Retry file processing operation with exponential backoff
 */
export async function retryFileProcessing<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  delayMs: number = 1000
): Promise<T> {
  let lastError: any;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;

      const fileError = FileErrorHandler.handle(error);

      // Don't retry if error is not recoverable
      if (!fileError.recoverable) {
        throw fileError;
      }

      // Don't retry on last attempt
      if (attempt === maxRetries - 1) {
        break;
      }

      // Wait with exponential backoff
      await new Promise(resolve => setTimeout(resolve, delayMs * Math.pow(2, attempt)));
    }
  }

  throw FileErrorHandler.handle(lastError);
}
