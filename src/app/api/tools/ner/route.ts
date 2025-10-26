import { NextRequest, NextResponse } from 'next/server';
import { NERProcessor } from '@/lib/tools/ner';
import { extractLegalEntities } from '@/lib/ml/ner-processor';
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

    const startTime = performance.now();

    // Use ML-based entity extraction for general entities
    const mlEntities = await extractLegalEntities(text);

    // Use specialized extractors for legal-specific entities
    const dates = await NERProcessor.extractDates(text);
    const monetaryAmounts = await NERProcessor.extractMonetaryAmounts(text);
    const parties = await NERProcessor.extractParties(text);

    // Combine ML and regex-based results
    const combinedEntities = {
      PERSON: mlEntities.parties.map(e => e.text),
      ORGANIZATION: mlEntities.organizations.map(e => e.text),
      LOCATION: mlEntities.locations.map(e => e.text),
      DATE: [...new Set([...mlEntities.dates.map(e => e.text), ...dates.dates])],
      MONEY: monetaryAmounts.amounts,
      // Keep additional ML entities
      ALL_ML: mlEntities.allEntities,
    };

    const processingTime = performance.now() - startTime;

    return NextResponse.json({
      success: true,
      entities: combinedEntities,
      parties,
      dates,
      monetaryAmounts,
      mlConfidence: mlEntities.allEntities.length > 0
        ? mlEntities.allEntities.reduce((sum, e) => sum + e.score, 0) / mlEntities.allEntities.length
        : 0,
      metadata: {
        textLength: text.length,
        processingTime,
        mlEntitiesCount: mlEntities.allEntities.length,
        method: 'hybrid-ml',
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
