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

    // Check file type
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!allowedTypes.includes(file.type)) {
      return NextResponse.json(
        { error: 'Unsupported file type. Only PDF and DOCX files are supported.' },
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

    // Convert file to buffer
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // Parse the document
    const result = await DocumentParser.parseDocument(buffer, file.name);

    if (!result.success) {
      return NextResponse.json(
        { 
          error: result.error || 'Document parsing failed',
          success: false,
        },
        { status: 400 }
      );
    }

    // Extract key sections
    const keySections = DocumentParser.extractKeySections(result.text);
    const readingTime = DocumentParser.calculateReadingTime(result.text);

    return NextResponse.json({
      success: true,
      text: result.text,
      metadata: {
        ...result.metadata,
        readingTime,
        keySections,
      },
      preview: DocumentParser.extractTextPreview(result.text),
    });

  } catch (error: any) {
    console.error('Document extraction API error:', error);
    
    return NextResponse.json(
      { 
        error: error.message || 'Document extraction failed',
        success: false,
      },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    message: 'Document extraction API endpoint',
    supportedFormats: ['PDF', 'DOCX'],
    maxFileSize: '10MB',
  });
}
