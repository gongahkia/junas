/**
 * PDF processing utilities with metadata extraction
 */

// Setup canvas polyfills for Node.js environment
let canvasPolyfillsLoaded = false;
async function setupCanvasPolyfills() {
  if (canvasPolyfillsLoaded) return;

  try {
    // Minimal polyfills for pdf.js canvas operations
    // These are used by pdf.js but not required for text extraction
    if (typeof globalThis.DOMMatrix === 'undefined') {
      // @ts-ignore - Minimal DOMMatrix polyfill
      globalThis.DOMMatrix = class DOMMatrix {
        a = 1; b = 0; c = 0; d = 1; e = 0; f = 0;
        constructor(values?: any) {
          if (Array.isArray(values)) {
            this.a = values[0] || 1;
            this.b = values[1] || 0;
            this.c = values[2] || 0;
            this.d = values[3] || 1;
            this.e = values[4] || 0;
            this.f = values[5] || 0;
          }
        }
        scale(x: number, y?: number) { return this; }
        translate(x: number, y: number) { return this; }
        multiply(other: any) { return this; }
      };
    }

    if (typeof globalThis.ImageData === 'undefined') {
      // @ts-ignore - Minimal ImageData polyfill
      globalThis.ImageData = class ImageData {
        width: number;
        height: number;
        data: Uint8ClampedArray;
        constructor(width: number, height: number) {
          this.width = width;
          this.height = height;
          this.data = new Uint8ClampedArray(width * height * 4);
        }
      };
    }

    if (typeof globalThis.Path2D === 'undefined') {
      // @ts-ignore - Minimal Path2D polyfill
      globalThis.Path2D = class Path2D {
        moveTo(x: number, y: number) {}
        lineTo(x: number, y: number) {}
        bezierCurveTo(cp1x: number, cp1y: number, cp2x: number, cp2y: number, x: number, y: number) {}
        closePath() {}
      };
    }

    canvasPolyfillsLoaded = true;
  } catch (error) {
    console.warn('Failed to load canvas polyfills:', error);
  }
}

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
    // Setup canvas polyfills before loading pdf-parse
    await setupCanvasPolyfills();

    // Dynamic import to avoid loading in wrong context
    const pdfParse = await import('pdf-parse');
    const pdf = (pdfParse as any).default || pdfParse;

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
