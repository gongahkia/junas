import { NextRequest, NextResponse } from 'next/server';
import { NERProcessor } from '@/lib/tools/ner';
import { NERRequestSchema, validateData } from '@/lib/validation';
import { sanitizePlainText } from '@/lib/sanitize';
import { formatErrorResponse } from '@/lib/api-utils';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate input with Zod schema
    const validation = validateData(NERRequestSchema, body);
    if (!validation.success) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      );
    }

    // Sanitize text input
    const text = sanitizePlainText(validation.data.text);

    // Extract entities
    const entities = await NERProcessor.extractEntities(text);
    
    // Extract additional information
    const parties = await NERProcessor.extractParties(text);
    const dates = await NERProcessor.extractDates(text);
    const monetaryAmounts = await NERProcessor.extractMonetaryAmounts(text);

    return NextResponse.json({
      success: true,
      entities,
      parties,
      dates,
      monetaryAmounts,
      metadata: {
        textLength: text.length,
        processingTime: Date.now(),
      },
    });

  } catch (error: any) {
    return NextResponse.json(
      formatErrorResponse(error, 'NER processing'),
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    message: 'NER API endpoint',
    supportedEntityTypes: ['PERSON', 'ORG', 'DATE', 'MONEY', 'LAW', 'GPE'],
    maxTextLength: '100,000 characters',
  });
}
