import { NextRequest, NextResponse } from 'next/server';
import { NERProcessor } from '@/lib/tools/ner';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { text } = body;

    if (!text || typeof text !== 'string') {
      return NextResponse.json(
        { error: 'Text is required' },
        { status: 400 }
      );
    }

    if (text.length > 100000) {
      return NextResponse.json(
        { error: 'Text too long. Maximum length is 100,000 characters.' },
        { status: 400 }
      );
    }

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
    console.error('NER API error:', error);
    
    return NextResponse.json(
      { 
        error: error.message || 'NER processing failed',
        success: false,
      },
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
