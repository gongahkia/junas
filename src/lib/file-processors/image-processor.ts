import Tesseract from 'tesseract.js';

/**
 * Image processing utilities with OCR support
 */

export interface OCRResult {
  text: string;
  confidence: number;
  wordCount: number;
  readingTimeMinutes: number;
  language: string;
}

export interface ImageProcessingResult {
  text: string;
  confidence: number;
  metadata: {
    wordCount: number;
    readingTimeMinutes: number;
    language: string;
    hasText: boolean;
  };
  success: boolean;
  error?: string;
}

/**
 * Process image file and extract text using OCR
 */
export async function processImage(
  buffer: Buffer,
  language: string = 'eng'
): Promise<ImageProcessingResult> {
  try {
    // Perform OCR using Tesseract with explicit worker paths
    const result = await Tesseract.recognize(buffer, language, {
      workerPath: 'https://cdn.jsdelivr.net/npm/tesseract.js@6.0.1/dist/worker.min.js',
      langPath: 'https://tessdata.projectnaptha.com/4.0.0',
      corePath: 'https://cdn.jsdelivr.net/npm/tesseract.js-core@6.0.1/tesseract-core.wasm.js',
      logger: (m) => {
        // Optional: Log progress
        if (m.status === 'recognizing text') {
          console.log(`OCR Progress: ${Math.round(m.progress * 100)}%`);
        }
      },
    });

    const cleanText = cleanOCRText(result.data.text);
    const wordCount = countWords(cleanText);
    const readingTimeMinutes = calculateReadingTime(wordCount);

    return {
      text: cleanText,
      confidence: result.data.confidence,
      metadata: {
        wordCount,
        readingTimeMinutes,
        language,
        hasText: wordCount > 0,
      },
      success: true,
    };
  } catch (error) {
    return {
      text: '',
      confidence: 0,
      metadata: {
        wordCount: 0,
        readingTimeMinutes: 0,
        language,
        hasText: false,
      },
      success: false,
      error: error instanceof Error ? error.message : 'Unknown OCR error',
    };
  }
}

/**
 * Process multiple images in batch
 */
export async function processBatchImages(
  buffers: Buffer[],
  language: string = 'eng'
): Promise<ImageProcessingResult[]> {
  const results: ImageProcessingResult[] = [];

  for (const buffer of buffers) {
    const result = await processImage(buffer, language);
    results.push(result);
  }

  return results;
}

/**
 * Detect if image likely contains text
 */
export async function detectTextInImage(buffer: Buffer): Promise<boolean> {
  try {
    const result = await processImage(buffer, 'eng');
    // Consider image to have text if confidence > 60 and word count > 5
    return result.confidence > 60 && result.metadata.wordCount > 5;
  } catch {
    return false;
  }
}

/**
 * Extract structured data from scanned legal documents
 */
export async function extractLegalDocument(
  buffer: Buffer
): Promise<{
  text: string;
  sections: Array<{ title: string; content: string }>;
  dates: string[];
  references: string[];
}> {
  const result = await processImage(buffer, 'eng');

  if (!result.success) {
    return {
      text: '',
      sections: [],
      dates: [],
      references: [],
    };
  }

  const sections = extractSections(result.text);
  const dates = extractDates(result.text);
  const references = extractReferences(result.text);

  return {
    text: result.text,
    sections,
    dates,
    references,
  };
}

/**
 * Clean OCR text by fixing common recognition errors
 */
function cleanOCRText(text: string): string {
  return text
    // Remove multiple consecutive newlines
    .replace(/\n{3,}/g, '\n\n')
    // Remove multiple consecutive spaces
    .replace(/  +/g, ' ')
    // Fix common OCR errors
    .replace(/\bl\b/g, 'I')  // Lowercase l often mistaken for I
    .replace(/\b0\b/g, 'O')  // Zero often mistaken for O in words
    // Remove spaces before punctuation
    .replace(/\s+([.,;:!?])/g, '$1')
    // Ensure space after punctuation
    .replace(/([.,;:!?])([A-Za-z])/g, '$1 $2')
    // Remove spaces at line endings
    .replace(/ +\n/g, '\n')
    // Trim
    .trim();
}

/**
 * Extract sections from OCR text
 */
function extractSections(text: string): Array<{ title: string; content: string }> {
  const sections: Array<{ title: string; content: string }> = [];
  const lines = text.split('\n');

  // Common heading patterns
  const headingPatterns = [
    /^[A-Z][A-Z\s]{10,}$/,  // ALL CAPS headings
    /^\d+\.\s+[A-Z]/,       // Numbered sections
    /^SECTION\s+\d+/i,
    /^ARTICLE\s+\d+/i,
    /^PART\s+[IVX]+/i,
  ];

  let currentTitle = '';
  let currentContent: string[] = [];

  for (const line of lines) {
    const trimmedLine = line.trim();
    let isHeading = false;

    if (trimmedLine.length > 0 && trimmedLine.length < 100) {
      for (const pattern of headingPatterns) {
        if (pattern.test(trimmedLine)) {
          // Save previous section
          if (currentTitle) {
            sections.push({
              title: currentTitle,
              content: currentContent.join('\n').trim(),
            });
          }

          currentTitle = trimmedLine;
          currentContent = [];
          isHeading = true;
          break;
        }
      }
    }

    if (!isHeading && trimmedLine.length > 0) {
      currentContent.push(trimmedLine);
    }
  }

  // Save last section
  if (currentTitle) {
    sections.push({
      title: currentTitle,
      content: currentContent.join('\n').trim(),
    });
  }

  return sections;
}

/**
 * Extract dates from text (common legal date formats)
 */
function extractDates(text: string): string[] {
  const datePatterns = [
    /\d{1,2}\/\d{1,2}\/\d{2,4}/g,           // MM/DD/YYYY
    /\d{1,2}-\d{1,2}-\d{2,4}/g,             // MM-DD-YYYY
    /\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}/gi,  // DD Month YYYY
    /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}/gi, // Month DD, YYYY
  ];

  const dates: Set<string> = new Set();

  for (const pattern of datePatterns) {
    const matches = text.match(pattern);
    if (matches) {
      matches.forEach(date => dates.add(date));
    }
  }

  return Array.from(dates);
}

/**
 * Extract legal references (case citations, statutes)
 */
function extractReferences(text: string): string[] {
  const referencePatterns = [
    /\[\d{4}\]\s+\w+\s+\d+/g,              // [YYYY] Court Number
    /\(\d{4}\)\s+\w+\s+\d+/g,              // (YYYY) Court Number
    /[A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+/g,  // Case names (Party v Party)
    /Cap\.\s*\d+[A-Z]?/g,                   // Singapore chapter references
  ];

  const references: Set<string> = new Set();

  for (const pattern of referencePatterns) {
    const matches = text.match(pattern);
    if (matches) {
      matches.forEach(ref => references.add(ref));
    }
  }

  return Array.from(references);
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
 * Validate image buffer before processing
 */
export function isValidImageBuffer(buffer: Buffer): boolean {
  if (buffer.length < 8) {
    return false;
  }

  // Check common image signatures
  const signatures = {
    png: Buffer.from([0x89, 0x50, 0x4e, 0x47]),
    jpg: Buffer.from([0xff, 0xd8, 0xff]),
    gif: Buffer.from([0x47, 0x49, 0x46]),
    bmp: Buffer.from([0x42, 0x4d]),
    tiff: Buffer.from([0x49, 0x49, 0x2a, 0x00]),
  };

  for (const [_, signature] of Object.entries(signatures)) {
    if (buffer.subarray(0, signature.length).equals(signature)) {
      return true;
    }
  }

  return false;
}

/**
 * Get supported OCR languages
 */
export function getSupportedLanguages(): string[] {
  return [
    'eng', // English
    'chi_sim', // Simplified Chinese
    'chi_tra', // Traditional Chinese
    'spa', // Spanish
    'fra', // French
    'deu', // German
    'jpn', // Japanese
    'kor', // Korean
    'rus', // Russian
    'ara', // Arabic
  ];
}
