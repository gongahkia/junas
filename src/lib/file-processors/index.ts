import { processPDF, isValidPDFBuffer, PDFProcessingResult } from './pdf-processor';
import { processDOCX, processDOCXWithStyles, isValidDOCXBuffer, DOCXProcessingResult } from './docx-processor';
import { processImage, isValidImageBuffer, ImageProcessingResult } from './image-processor';
import { validateFileType } from '@/lib/file-validation';

/**
 * Unified file processing pipeline
 */

export type FileType = 'pdf' | 'docx' | 'image' | 'unknown';

export interface UnifiedProcessingResult {
  text: string;
  html?: string;
  fileType: FileType;
  metadata: {
    wordCount: number;
    readingTimeMinutes: number;
    [key: string]: any;
  };
  success: boolean;
  error?: string;
  warnings?: string[];
}

/**
 * Process file based on type detection
 */
export async function processFile(
  buffer: Buffer,
  filename: string,
  options: {
    ocrLanguage?: string;
    preserveStyles?: boolean;
  } = {}
): Promise<UnifiedProcessingResult> {
  try {
    // Validate and detect file type using magic numbers
    const fileTypeResult = await validateFileType(buffer, filename);

    if (!fileTypeResult.valid) {
      return {
        text: '',
        fileType: 'unknown',
        metadata: { wordCount: 0, readingTimeMinutes: 0 },
        success: false,
        error: fileTypeResult.error || 'Invalid file type',
      };
    }

    const fileType = detectFileType(buffer, filename);

    // Route to appropriate processor
    switch (fileType) {
      case 'pdf':
        return await processPDFFile(buffer);

      case 'docx':
        return await processDOCXFile(buffer, options.preserveStyles);

      case 'image':
        return await processImageFile(buffer, options.ocrLanguage);

      default:
        return {
          text: '',
          fileType: 'unknown',
          metadata: { wordCount: 0, readingTimeMinutes: 0 },
          success: false,
          error: 'Unsupported file type',
        };
    }
  } catch (error) {
    return {
      text: '',
      fileType: 'unknown',
      metadata: { wordCount: 0, readingTimeMinutes: 0 },
      success: false,
      error: error instanceof Error ? error.message : 'Unknown processing error',
    };
  }
}

/**
 * Process multiple files in batch
 */
export async function processBatchFiles(
  files: Array<{ buffer: Buffer; filename: string }>,
  options: {
    ocrLanguage?: string;
    preserveStyles?: boolean;
  } = {}
): Promise<UnifiedProcessingResult[]> {
  const results: UnifiedProcessingResult[] = [];

  for (const file of files) {
    const result = await processFile(file.buffer, file.filename, options);
    results.push(result);
  }

  return results;
}

/**
 * Process PDF file
 */
async function processPDFFile(buffer: Buffer): Promise<UnifiedProcessingResult> {
  if (!isValidPDFBuffer(buffer)) {
    return {
      text: '',
      fileType: 'pdf',
      metadata: { wordCount: 0, readingTimeMinutes: 0 },
      success: false,
      error: 'Invalid PDF file',
    };
  }

  const result = await processPDF(buffer);

  return {
    text: result.text,
    fileType: 'pdf',
    metadata: {
      wordCount: result.wordCount,
      readingTimeMinutes: result.readingTimeMinutes,
      pageCount: result.pageCount,
      pdfMetadata: result.metadata,
    },
    success: result.success,
    error: result.error,
  };
}

/**
 * Process DOCX file
 */
async function processDOCXFile(
  buffer: Buffer,
  preserveStyles: boolean = false
): Promise<UnifiedProcessingResult> {
  if (!isValidDOCXBuffer(buffer)) {
    return {
      text: '',
      fileType: 'docx',
      metadata: { wordCount: 0, readingTimeMinutes: 0 },
      success: false,
      error: 'Invalid DOCX file',
    };
  }

  const result = preserveStyles
    ? await processDOCXWithStyles(buffer)
    : await processDOCX(buffer);

  return {
    text: result.text,
    html: result.html,
    fileType: 'docx',
    metadata: {
      wordCount: result.metadata.wordCount,
      readingTimeMinutes: result.metadata.readingTimeMinutes,
      docxMetadata: result.metadata,
    },
    success: result.success,
    error: result.error,
    warnings: result.warnings,
  };
}

/**
 * Process image file with OCR
 */
async function processImageFile(
  buffer: Buffer,
  language: string = 'eng'
): Promise<UnifiedProcessingResult> {
  if (!isValidImageBuffer(buffer)) {
    return {
      text: '',
      fileType: 'image',
      metadata: { wordCount: 0, readingTimeMinutes: 0 },
      success: false,
      error: 'Invalid image file',
    };
  }

  const result = await processImage(buffer, language);

  return {
    text: result.text,
    fileType: 'image',
    metadata: {
      wordCount: result.metadata.wordCount,
      readingTimeMinutes: result.metadata.readingTimeMinutes,
      ocrConfidence: result.confidence,
      language: result.metadata.language,
    },
    success: result.success,
    error: result.error,
  };
}

/**
 * Detect file type from buffer and filename
 */
function detectFileType(buffer: Buffer, filename: string): FileType {
  // Check magic numbers first (most reliable)
  if (isValidPDFBuffer(buffer)) {
    return 'pdf';
  }

  if (isValidDOCXBuffer(buffer)) {
    return 'docx';
  }

  if (isValidImageBuffer(buffer)) {
    return 'image';
  }

  // Fallback to extension
  const extension = filename.split('.').pop()?.toLowerCase();

  switch (extension) {
    case 'pdf':
      return 'pdf';
    case 'docx':
    case 'doc':
      return 'docx';
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'bmp':
    case 'tiff':
      return 'image';
    default:
      return 'unknown';
  }
}

/**
 * Get processing statistics for multiple files
 */
export function getProcessingStats(results: UnifiedProcessingResult[]): {
  totalFiles: number;
  successfulFiles: number;
  failedFiles: number;
  totalWords: number;
  totalReadingTime: number;
  fileTypeBreakdown: Record<FileType, number>;
} {
  const stats = {
    totalFiles: results.length,
    successfulFiles: 0,
    failedFiles: 0,
    totalWords: 0,
    totalReadingTime: 0,
    fileTypeBreakdown: {
      pdf: 0,
      docx: 0,
      image: 0,
      unknown: 0,
    } as Record<FileType, number>,
  };

  for (const result of results) {
    if (result.success) {
      stats.successfulFiles++;
      stats.totalWords += result.metadata.wordCount;
      stats.totalReadingTime += result.metadata.readingTimeMinutes;
    } else {
      stats.failedFiles++;
    }

    stats.fileTypeBreakdown[result.fileType]++;
  }

  return stats;
}

/**
 * Export all processors for direct use
 */
export {
  processPDF,
  processDOCX,
  processDOCXWithStyles,
  processImage,
  isValidPDFBuffer,
  isValidDOCXBuffer,
  isValidImageBuffer,
};

export type {
  PDFProcessingResult,
  DOCXProcessingResult,
  ImageProcessingResult,
};
