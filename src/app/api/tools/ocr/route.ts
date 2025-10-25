import { NextRequest, NextResponse } from 'next/server';
import { OCRProcessor } from '@/lib/tools/ocr';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;
    
    if (!file) {
      return NextResponse.json(
        { error: 'No file provided' },
        { status: 400 }
      );
    }

    // Check file type
    if (!file.type.startsWith('image/')) {
      return NextResponse.json(
        { error: 'File must be an image' },
        { status: 400 }
      );
    }

    // Check file size (10MB limit)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      return NextResponse.json(
        { error: 'File too large. Maximum size is 10MB.' },
        { status: 400 }
      );
    }

    // Process the image
    const result = await OCRProcessor.extractTextFromImageFile(file);

    return NextResponse.json({
      success: true,
      text: result.text,
      confidence: result.confidence,
      boundingBoxes: result.boundingBoxes,
      metadata: {
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
      },
    });

  } catch (error: any) {
    console.error('OCR API error:', error);
    
    return NextResponse.json(
      { 
        error: error.message || 'OCR processing failed',
        success: false,
      },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    message: 'OCR API endpoint',
    supportedFormats: ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'],
    maxFileSize: '10MB',
  });
}
