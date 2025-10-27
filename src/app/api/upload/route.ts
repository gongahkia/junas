import { NextRequest, NextResponse } from 'next/server';

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

    // Check file size (10MB limit)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      return NextResponse.json(
        { error: 'File too large. Maximum size is 10MB.' },
        { status: 400 }
      );
    }

    // Check file type
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'image/jpeg',
      'image/png',
      'image/gif',
      'image/bmp',
      'image/webp',
    ];

    if (!allowedTypes.includes(file.type)) {
      return NextResponse.json(
        { error: 'Unsupported file type. Only PDF, DOCX, and image files are supported.' },
        { status: 400 }
      );
    }

    // Return success - file processing happens client-side
    // This avoids issues with pdf-parse and mammoth in Next.js API routes
    return NextResponse.json({
      success: true,
      text: '',
      metadata: {
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
      },
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
