import * as pdfParse from 'pdf-parse';
import * as mammoth from 'mammoth';

export interface ParsedDocument {
  text: string;
  metadata: {
    title?: string;
    author?: string;
    creationDate?: Date;
    pageCount?: number;
    wordCount: number;
  };
  success: boolean;
  error?: string;
}

export class DocumentParser {
  static async parsePDF(buffer: Buffer): Promise<ParsedDocument> {
    try {
      const data = await pdfParse(buffer);
      
      return {
        text: data.text,
        metadata: {
          title: data.info?.Title,
          author: data.info?.Author,
          creationDate: data.info?.CreationDate ? new Date(data.info.CreationDate) : undefined,
          pageCount: data.numpages,
          wordCount: data.text.split(/\s+/).length,
        },
        success: true,
      };
    } catch (error: any) {
      return {
        text: '',
        metadata: { wordCount: 0 },
        success: false,
        error: error.message || 'Failed to parse PDF',
      };
    }
  }

  static async parseDOCX(buffer: Buffer): Promise<ParsedDocument> {
    try {
      const result = await mammoth.extractRawText({ buffer });
      
      return {
        text: result.value,
        metadata: {
          wordCount: result.value.split(/\s+/).length,
        },
        success: true,
      };
    } catch (error: any) {
      return {
        text: '',
        metadata: { wordCount: 0 },
        success: false,
        error: error.message || 'Failed to parse DOCX',
      };
    }
  }

  static async parseDocument(
    buffer: Buffer,
    filename: string
  ): Promise<ParsedDocument> {
    const extension = filename.split('.').pop()?.toLowerCase();
    
    switch (extension) {
      case 'pdf':
        return this.parsePDF(buffer);
      case 'docx':
        return this.parseDOCX(buffer);
      default:
        return {
          text: '',
          metadata: { wordCount: 0 },
          success: false,
          error: `Unsupported file type: ${extension}`,
        };
    }
  }

  static extractTextPreview(text: string, maxLength: number = 200): string {
    if (text.length <= maxLength) return text;
    
    // Try to break at word boundary
    const truncated = text.substring(0, maxLength);
    const lastSpace = truncated.lastIndexOf(' ');
    
    if (lastSpace > maxLength * 0.8) {
      return truncated.substring(0, lastSpace) + '...';
    }
    
    return truncated + '...';
  }

  static extractKeySections(text: string): {
    title?: string;
    parties?: string[];
    dates?: string[];
    clauses?: string[];
  } {
    const sections: any = {};
    
    // Extract title (usually first line or after common patterns)
    const titleMatch = text.match(/^(?:TITLE|Title|CONTRACT|Agreement|Agreement)\s*:?\s*(.+)$/m);
    if (titleMatch) {
      sections.title = titleMatch[1].trim();
    }
    
    // Extract parties (look for "between" or "and" patterns)
    const partyMatches = text.match(/(?:between|BETWEEN)\s+([^,]+(?:\s+and\s+[^,]+)*)/gi);
    if (partyMatches) {
      sections.parties = partyMatches.map(match => 
        match.replace(/(?:between|BETWEEN)\s+/i, '').trim()
      );
    }
    
    // Extract dates (common date patterns)
    const datePattern = /(?:\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})/gi;
    const dateMatches = text.match(datePattern);
    if (dateMatches) {
      sections.dates = [...new Set(dateMatches)]; // Remove duplicates
    }
    
    // Extract clause headers
    const clausePattern = /(?:Section|Clause|Article)\s+\d+[\.:]?\s*([^\n]+)/gi;
    const clauseMatches = text.match(clausePattern);
    if (clauseMatches) {
      sections.clauses = clauseMatches.map(match => match.trim());
    }
    
    return sections;
  }

  static calculateReadingTime(text: string): number {
    const wordsPerMinute = 200;
    const wordCount = text.split(/\s+/).length;
    return Math.ceil(wordCount / wordsPerMinute);
  }
}
