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

    // Return success - file processing happens client-side
    // This avoids issues with pdf-parse and mammoth in Next.js API routes
    return NextResponse.json({
      success: true,
      text: '',
      metadata: {
        fileName: safeName,
        fileSize: file.size,
        fileType: file.type,
      },
      warnings: processingResult.warnings,
    });

  } catch (error: any) {
    console.error('File upload API error:', error);
    console.error('Error stack:', error.stack);
    console.error('Error details:', JSON.stringify(error, null, 2));

    return NextResponse.json(
      {
        error: error.message || 'File upload failed',
        errorDetails: error.toString(),
        success: false,
      },
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
