import { createWorker } from 'tesseract.js';
import { OCRResult, BoundingBox } from '@/types/tool';
import path from 'path';

export class OCRProcessor {
  private static worker: any = null;
  private static isInitialized = false;

  static async initialize(): Promise<void> {
    if (this.isInitialized) return;

    try {
      // Find the tesseract.js node_modules path dynamically
      const tesseractPath = path.dirname(require.resolve('tesseract.js'));

      this.worker = await createWorker('eng', 1, {
        workerPath: path.join(tesseractPath, 'src', 'worker-script', 'node', 'index.js'),
        corePath: path.join(tesseractPath, 'src', 'worker-script', 'node'),
      });
      this.isInitialized = true;
    } catch (error) {
      console.error('Failed to initialize OCR worker:', error);
      throw new Error('OCR initialization failed');
    }
  }

  static async processImage(imageData: string | File | Buffer): Promise<OCRResult> {
    if (!this.isInitialized) {
      await this.initialize();
    }

    try {
      const { data } = await this.worker.recognize(imageData);
      
      const boundingBoxes: BoundingBox[] = data.words.map((word: any) => ({
        x: word.bbox.x0,
        y: word.bbox.y0,
        width: word.bbox.x1 - word.bbox.x0,
        height: word.bbox.y1 - word.bbox.y0,
        text: word.text,
        confidence: word.confidence,
      }));

      return {
        text: data.text,
        confidence: data.confidence,
        boundingBoxes,
      };
    } catch (error: any) {
      console.error('OCR processing failed:', error);
      return {
        text: '',
        confidence: 0,
        error: error.message || 'OCR processing failed',
      };
    }
  }

  static async processPDFPages(pdfBuffer: Buffer): Promise<OCRResult[]> {
    // This would require pdf2pic or similar library to convert PDF pages to images
    // For now, return empty result
    console.warn('PDF OCR not implemented yet');
    return [];
  }

  static async terminate(): Promise<void> {
    if (this.worker) {
      await this.worker.terminate();
      this.worker = null;
      this.isInitialized = false;
    }
  }

  static async isImageFile(file: File): Promise<boolean> {
    const imageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'];
    return imageTypes.includes(file.type);
  }

  static async extractTextFromImageFile(file: File): Promise<OCRResult> {
    if (!(await this.isImageFile(file))) {
      throw new Error('File is not an image');
    }

    return this.processImage(file);
  }

  static async preprocessImage(imageData: string): Promise<string> {
    // Basic image preprocessing to improve OCR accuracy
    // This could include:
    // - Noise reduction
    // - Contrast enhancement
    // - Deskewing
    // - Binarization
    
    // For now, return as-is
    return imageData;
  }

  static async detectTextRegions(imageData: string): Promise<BoundingBox[]> {
    if (!this.isInitialized) {
      await this.initialize();
    }

    try {
      const { data } = await this.worker.detect(imageData);
      
      return data.words.map((word: any) => ({
        x: word.bbox.x0,
        y: word.bbox.y0,
        width: word.bbox.x1 - word.bbox.x0,
        height: word.bbox.y1 - word.bbox.y0,
        text: word.text,
        confidence: word.confidence,
      }));
    } catch (error) {
      console.error('Text region detection failed:', error);
      return [];
    }
  }

  static async getSupportedLanguages(): Promise<string[]> {
    if (!this.isInitialized) {
      await this.initialize();
    }

    try {
      return await this.worker.getAvailableLanguages();
    } catch (error) {
      console.error('Failed to get supported languages:', error);
      return ['eng']; // Default to English
    }
  }

  static async setLanguage(language: string): Promise<void> {
    if (!this.isInitialized) {
      await this.initialize();
    }

    try {
      await this.worker.loadLanguage(language);
      await this.worker.initialize(language);
    } catch (error) {
      console.error(`Failed to set language to ${language}:`, error);
    }
  }
}
