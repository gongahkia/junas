import { NextRequest, NextResponse } from 'next/server';
import { validateFile } from '@/lib/file-validation';
import { sanitizeFilename } from '@/lib/sanitize';
import { formatErrorResponse } from '@/lib/api-utils';
import { processFile } from '@/lib/file-processors';

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

    // Sanitize filename
    const safeName = sanitizeFilename(file.name);

    // Read file buffer for magic number validation
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // Validate file using magic numbers (not just MIME type)
    const validation = await validateFile({
      buffer,
      name: safeName,
      size: file.size,
    });

    if (!validation.valid) {
      return NextResponse.json(
        { error: validation.error || 'File validation failed' },
        { status: 400 }
      );
    }

    // Process file to extract text and metadata
    const processingResult = await processFile(buffer, safeName, {
      ocrLanguage: 'eng', // Default to English, could be parameterized
      preserveStyles: true, // Preserve formatting for legal documents
    });

    if (!processingResult.success) {
      return NextResponse.json(
        { error: processingResult.error || 'File processing failed' },
        { status: 500 }
      );
    }

    // Return processed file information
    return NextResponse.json({
      success: true,
      text: processingResult.text,
      html: processingResult.html,
      metadata: {
        fileName: safeName,
        fileSize: file.size,
        fileType: validation.mimeType,
        detectedExtension: validation.ext,
        wordCount: processingResult.metadata.wordCount,
        readingTimeMinutes: processingResult.metadata.readingTimeMinutes,
        processedAs: processingResult.fileType,
        ...processingResult.metadata,
      },
      warnings: processingResult.warnings,
    });

  } catch (error: any) {
    console.error('Upload error:', error);
    console.error('Error stack:', error.stack);
    return NextResponse.json(
      formatErrorResponse(error, 'File upload'),
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    message: 'File upload API endpoint',
    supportedFormats: ['PDF', 'DOCX', 'JPEG', 'PNG', 'GIF', 'BMP', 'WEBP'],
    maxFileSize: '10MB',
  });
}
