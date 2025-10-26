import pdf from 'pdf-parse';

/**
 * PDF processing utilities with metadata extraction
 */

export interface PDFMetadata {
  title?: string;
  author?: string;
  subject?: string;
  creator?: string;
  producer?: string;
  creationDate?: Date;
  modificationDate?: Date;
  pageCount: number;
}

export interface PDFProcessingResult {
  text: string;
  metadata: PDFMetadata;
  wordCount: number;
  readingTimeMinutes: number;
  pageCount: number;
  success: boolean;
  error?: string;
}

/**
 * Process PDF file and extract text with metadata
 */
export async function processPDF(buffer: Buffer): Promise<PDFProcessingResult> {
  try {
    const data = await pdf(buffer);

    // Extract metadata
    const metadata: PDFMetadata = {
      title: data.info?.Title,
      author: data.info?.Author,
      subject: data.info?.Subject,
      creator: data.info?.Creator,
      producer: data.info?.Producer,
      creationDate: data.info?.CreationDate ? new Date(data.info.CreationDate) : undefined,
      modificationDate: data.info?.ModDate ? new Date(data.info.ModDate) : undefined,
      pageCount: data.numpages,
    };

    // Clean and process text
    const cleanText = cleanPDFText(data.text);
    const wordCount = countWords(cleanText);
    const readingTimeMinutes = calculateReadingTime(wordCount);

    return {
      text: cleanText,
      metadata,
      wordCount,
      readingTimeMinutes,
      pageCount: data.numpages,
      success: true,
    };
  } catch (error) {
    return {
      text: '',
      metadata: { pageCount: 0 },
      wordCount: 0,
      readingTimeMinutes: 0,
      pageCount: 0,
      success: false,
      error: error instanceof Error ? error.message : 'Unknown PDF processing error',
    };
  }
}

/**
 * Clean PDF text by removing excessive whitespace and formatting artifacts
 */
function cleanPDFText(text: string): string {
  return text
    // Remove multiple consecutive newlines
    .replace(/\n{3,}/g, '\n\n')
    // Remove multiple consecutive spaces
    .replace(/  +/g, ' ')
    // Remove spaces at line endings
    .replace(/ +\n/g, '\n')
    // Trim
    .trim();
}

/**
 * Count words in text
 */
function countWords(text: string): number {
  return text.split(/\s+/).filter(word => word.length > 0).length;
}

/**
 * Calculate reading time based on average reading speed (250 words/min)
 */
function calculateReadingTime(wordCount: number): number {
  return Math.ceil(wordCount / 250);
}

/**
 * Extract document structure (sections and headings)
 */
export function extractDocumentStructure(text: string): {
  sections: Array<{ title: string; startIndex: number }>;
  hasTableOfContents: boolean;
} {
  const sections: Array<{ title: string; startIndex: number }> = [];
  const lines = text.split('\n');

  // Common heading patterns in legal documents
  const headingPatterns = [
    /^[A-Z][A-Z\s]{10,}$/,  // ALL CAPS headings
    /^\d+\.\s+[A-Z]/,       // Numbered sections (1. Introduction)
    /^SECTION\s+\d+/i,      // Section markers
    /^ARTICLE\s+\d+/i,      // Article markers
    /^PART\s+[IVX]+/i,      // Part markers (Roman numerals)
    /^CHAPTER\s+\d+/i,      // Chapter markers
  ];

  let currentIndex = 0;
  for (const line of lines) {
    const trimmedLine = line.trim();

    if (trimmedLine.length > 0 && trimmedLine.length < 100) {
      for (const pattern of headingPatterns) {
        if (pattern.test(trimmedLine)) {
          sections.push({
            title: trimmedLine,
            startIndex: currentIndex,
          });
          break;
        }
      }
    }

    currentIndex += line.length + 1; // +1 for newline
  }

  // Check for table of contents
  const hasTableOfContents = /table\s+of\s+contents/i.test(text.slice(0, 1000));

  return { sections, hasTableOfContents };
}

/**
 * Validate PDF buffer before processing
 */
export function isValidPDFBuffer(buffer: Buffer): boolean {
  // PDF files start with %PDF-
  if (buffer.length < 5) {
    return false;
  }

  const header = buffer.toString('utf8', 0, 5);
  return header === '%PDF-';
}
