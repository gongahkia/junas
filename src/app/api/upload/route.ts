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

    // For now, return a simple success response
    // File processing will be handled client-side to avoid server-side issues
    return NextResponse.json({
      success: true,
      text: `File "${file.name}" uploaded successfully. File processing will be implemented client-side.`,
      metadata: {
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
        wordCount: 0,
        readingTime: 0,
      },
    });

  } catch (error: any) {
    console.error('File upload API error:', error);
    
    return NextResponse.json(
      { 
        error: error.message || 'File upload failed',
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
