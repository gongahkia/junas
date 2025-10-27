import * as pdfParse from 'pdf-parse';
import * as mammoth from 'mammoth';

export interface ProcessedFile {
  text: string;
  metadata: {
    fileName: string;
    fileSize: number;
    fileType: string;
    wordCount?: number;
    readingTime?: number;
    pageCount?: number;
  };
}

export class FileProcessor {
  /**
   * Process a PDF file client-side
   */
  static async processPDF(file: File): Promise<ProcessedFile> {
    try {
      const arrayBuffer = await file.arrayBuffer();
      const data = await pdfParse(Buffer.from(arrayBuffer));

      const wordCount = data.text.split(/\s+/).filter(w => w.length > 0).length;
      const readingTime = Math.ceil(wordCount / 200); // 200 words per minute

      return {
        text: data.text,
        metadata: {
          fileName: file.name,
          fileSize: file.size,
          fileType: file.type,
          wordCount,
          readingTime,
          pageCount: data.numpages,
        },
      };
    } catch (error: any) {
      console.error('PDF processing error:', error);
      throw new Error(`Failed to process PDF: ${error.message}`);
    }
  }

  /**
   * Process a DOCX file client-side
   */
  static async processDOCX(file: File): Promise<ProcessedFile> {
    try {
      const arrayBuffer = await file.arrayBuffer();
      const result = await mammoth.extractRawText({ arrayBuffer });

      const wordCount = result.value.split(/\s+/).filter(w => w.length > 0).length;
      const readingTime = Math.ceil(wordCount / 200); // 200 words per minute

      return {
        text: result.value,
        metadata: {
          fileName: file.name,
          fileSize: file.size,
          fileType: file.type,
          wordCount,
          readingTime,
        },
      };
    } catch (error: any) {
      console.error('DOCX processing error:', error);
      throw new Error(`Failed to process DOCX: ${error.message}`);
    }
  }

  /**
   * Process an image file (returns placeholder, actual OCR would be separate)
   */
  static async processImage(file: File): Promise<ProcessedFile> {
    return {
      text: `[Image file: ${file.name}]`,
      metadata: {
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
      },
    };
  }

  /**
   * Process any supported file type
   */
  static async processFile(file: File): Promise<ProcessedFile> {
    if (file.type === 'application/pdf') {
      return this.processPDF(file);
    }

    if (file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
      return this.processDOCX(file);
    }

    if (file.type.startsWith('image/')) {
      return this.processImage(file);
    }

    throw new Error(`Unsupported file type: ${file.type}`);
  }
}
