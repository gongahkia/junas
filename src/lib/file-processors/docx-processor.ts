import mammoth from 'mammoth';

/**
 * DOCX processing utilities with enhanced text extraction
 */

export interface DOCXMetadata {
  wordCount: number;
  readingTimeMinutes: number;
  hasImages: boolean;
  hasTables: boolean;
  hasFootnotes: boolean;
}

export interface DOCXProcessingResult {
  text: string;
  html: string;
  metadata: DOCXMetadata;
  success: boolean;
  error?: string;
  warnings: string[];
}

/**
 * Process DOCX file and extract text with formatting
 */
export async function processDOCX(buffer: Buffer): Promise<DOCXProcessingResult> {
  try {
    // Extract text with basic formatting preserved as HTML
    const result = await mammoth.convertToHtml({ buffer });

    // Also extract plain text for word counting
    const textResult = await mammoth.extractRawText({ buffer });

    const cleanText = cleanDOCXText(textResult.value);
    const wordCount = countWords(cleanText);
    const readingTimeMinutes = calculateReadingTime(wordCount);

    // Analyze document features
    const metadata: DOCXMetadata = {
      wordCount,
      readingTimeMinutes,
      hasImages: result.value.includes('<img'),
      hasTables: result.value.includes('<table'),
      hasFootnotes: result.value.includes('footnote'),
    };

    return {
      text: cleanText,
      html: result.value,
      metadata,
      success: true,
      warnings: result.messages.map(msg => msg.message),
    };
  } catch (error) {
    return {
      text: '',
      html: '',
      metadata: {
        wordCount: 0,
        readingTimeMinutes: 0,
        hasImages: false,
        hasTables: false,
        hasFootnotes: false,
      },
      success: false,
      error: error instanceof Error ? error.message : 'Unknown DOCX processing error',
      warnings: [],
    };
  }
}

/**
 * Process DOCX with custom style mapping for legal documents
 */
export async function processDOCXWithStyles(buffer: Buffer): Promise<DOCXProcessingResult> {
  try {
    // Custom style mapping for legal documents
    const styleMap = [
      // Preserve heading hierarchy
      "p[style-name='Heading 1'] => h1:fresh",
      "p[style-name='Heading 2'] => h2:fresh",
      "p[style-name='Heading 3'] => h3:fresh",

      // Preserve lists
      "p[style-name='List Paragraph'] => ul > li:fresh",

      // Preserve emphasis
      "b => strong",
      "i => em",

      // Preserve tables
      "table => table.legal-table",
    ].join('\n');

    const result = await mammoth.convertToHtml(
      { buffer },
      { styleMap }
    );

    const textResult = await mammoth.extractRawText({ buffer });
    const cleanText = cleanDOCXText(textResult.value);
    const wordCount = countWords(cleanText);
    const readingTimeMinutes = calculateReadingTime(wordCount);

    const metadata: DOCXMetadata = {
      wordCount,
      readingTimeMinutes,
      hasImages: result.value.includes('<img'),
      hasTables: result.value.includes('<table'),
      hasFootnotes: result.value.includes('footnote'),
    };

    return {
      text: cleanText,
      html: result.value,
      metadata,
      success: true,
      warnings: result.messages.map(msg => msg.message),
    };
  } catch (error) {
    return {
      text: '',
      html: '',
      metadata: {
        wordCount: 0,
        readingTimeMinutes: 0,
        hasImages: false,
        hasTables: false,
        hasFootnotes: false,
      },
      success: false,
      error: error instanceof Error ? error.message : 'Unknown DOCX processing error',
      warnings: [],
    };
  }
}

/**
 * Extract document sections from DOCX HTML
 */
export function extractDOCXSections(html: string): Array<{
  title: string;
  level: number;
  content: string;
}> {
  const sections: Array<{ title: string; level: number; content: string }> = [];

  // Match heading tags and their content
  const headingRegex = /<(h[1-6])>(.*?)<\/\1>/gi;
  let match;

  while ((match = headingRegex.exec(html)) !== null) {
    const level = parseInt(match[1].substring(1));
    const title = match[2].replace(/<[^>]+>/g, '').trim();

    // Extract content until next heading
    const startIndex = match.index + match[0].length;
    const nextHeadingIndex = html.slice(startIndex).search(/<h[1-6]>/i);
    const endIndex = nextHeadingIndex === -1
      ? html.length
      : startIndex + nextHeadingIndex;

    const content = html.slice(startIndex, endIndex)
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    sections.push({ title, level, content });
  }

  return sections;
}

/**
 * Clean DOCX text by removing excessive whitespace
 */
function cleanDOCXText(text: string): string {
  return text
    // Remove multiple consecutive newlines
    .replace(/\n{3,}/g, '\n\n')
    // Remove multiple consecutive spaces
    .replace(/  +/g, ' ')
    // Remove spaces at line endings
    .replace(/ +\n/g, '\n')
    // Remove carriage returns
    .replace(/\r/g, '')
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
 * Validate DOCX buffer before processing
 */
export function isValidDOCXBuffer(buffer: Buffer): boolean {
  // DOCX files are ZIP archives with specific signature
  if (buffer.length < 4) {
    return false;
  }

  // Check for ZIP file signature (PK)
  const signature = buffer.toString('hex', 0, 2);
  return signature === '504b'; // 'PK' in hex
}

/**
 * Extract tables from DOCX HTML
 */
export function extractDOCXTables(html: string): Array<{
  rows: string[][];
  caption?: string;
}> {
  const tables: Array<{ rows: string[][]; caption?: string }> = [];
  const tableRegex = /<table[^>]*>(.*?)<\/table>/gis;
  let match;

  while ((match = tableRegex.exec(html)) !== null) {
    const tableHTML = match[1];
    const rows: string[][] = [];

    // Extract rows
    const rowRegex = /<tr[^>]*>(.*?)<\/tr>/gis;
    let rowMatch;

    while ((rowMatch = rowRegex.exec(tableHTML)) !== null) {
      const rowHTML = rowMatch[1];
      const cells: string[] = [];

      // Extract cells (both th and td)
      const cellRegex = /<t[hd][^>]*>(.*?)<\/t[hd]>/gis;
      let cellMatch;

      while ((cellMatch = cellRegex.exec(rowHTML)) !== null) {
        const cellText = cellMatch[1]
          .replace(/<[^>]+>/g, '')
          .trim();
        cells.push(cellText);
      }

      if (cells.length > 0) {
        rows.push(cells);
      }
    }

    if (rows.length > 0) {
      tables.push({ rows });
    }
  }

  return tables;
}
