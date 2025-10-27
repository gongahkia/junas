import { NextRequest, NextResponse } from 'next/server';
import { DocumentParser } from '@/lib/tools/document-parser';

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

    // Process document files (PDF, DOCX)
    if (file.type === 'application/pdf' ||
        file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {

      const arrayBuffer = await file.arrayBuffer();
      const buffer = Buffer.from(arrayBuffer);

      const parsed = await DocumentParser.parseDocument(buffer, file.name);

      if (!parsed.success) {
        return NextResponse.json(
          { error: parsed.error || 'Failed to parse document' },
          { status: 500 }
        );
      }

      return NextResponse.json({
        success: true,
        text: parsed.text,
        metadata: {
          fileName: file.name,
          fileSize: file.size,
          fileType: file.type,
          wordCount: parsed.metadata.wordCount,
          readingTime: DocumentParser.calculateReadingTime(parsed.text),
          pageCount: parsed.metadata.pageCount,
          title: parsed.metadata.title,
          author: parsed.metadata.author,
        },
      });
    }

    // For image files, return basic info (OCR will be handled separately if needed)
    if (file.type.startsWith('image/')) {
      return NextResponse.json({
        success: true,
        text: `[Image file: ${file.name}]`,
        metadata: {
          fileName: file.name,
          fileSize: file.size,
          fileType: file.type,
          wordCount: 0,
          readingTime: 0,
        },
      });
    }

    // Fallback for other file types
    return NextResponse.json({
      success: true,
      text: `[Attached file: ${file.name}]`,
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
