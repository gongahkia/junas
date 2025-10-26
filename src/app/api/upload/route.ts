import { NextRequest, NextResponse } from 'next/server';
import { validateFile } from '@/lib/file-validation';
import { sanitizeFilename } from '@/lib/sanitize';
import { formatErrorResponse } from '@/lib/api-utils';

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
    const buffer = await file.arrayBuffer();

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

    // Return validated file information
    return NextResponse.json({
      success: true,
      text: `File "${safeName}" uploaded and validated successfully.`,
      metadata: {
        fileName: safeName,
        fileSize: file.size,
        fileType: validation.mimeType,
        detectedExtension: validation.ext,
        wordCount: 0, // To be implemented in file processing task
        readingTime: 0, // To be implemented in file processing task
      },
    });

  } catch (error: any) {
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
