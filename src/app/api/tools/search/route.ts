import { NextRequest, NextResponse } from 'next/server';
import { LegalSearchEngine } from '@/lib/tools/legal-search';
import { SearchRequestSchema, validateData } from '@/lib/validation';
import { sanitizeSearchQuery } from '@/lib/sanitize';
import { formatErrorResponse } from '@/lib/api-utils';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate input with Zod schema
    const validation = validateData(SearchRequestSchema, body);
    if (!validation.success) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      );
    }

    // Sanitize search query
    const query = sanitizeSearchQuery(validation.data.query);
    const type = body.type;
    const topic = body.topic;

    let results;

    if (type === 'statutes') {
      results = await LegalSearchEngine.searchSingaporeStatutes(query);
    } else if (type === 'cases') {
      results = await LegalSearchEngine.searchCaseLaw(query);
    } else if (type === 'regulations') {
      results = await LegalSearchEngine.searchRegulations(query);
    } else if (topic) {
      results = await LegalSearchEngine.searchByTopic(topic);
    } else {
      results = await LegalSearchEngine.searchAll(query);
    }

    return NextResponse.json({
      success: true,
      results,
      metadata: {
        query,
        type,
        topic,
        resultCount: results.length,
        processingTime: Date.now(),
      },
    });

  } catch (error: any) {
    return NextResponse.json(
      formatErrorResponse(error, 'Legal search'),
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    message: 'Legal search API endpoint',
    supportedTypes: ['statutes', 'cases', 'regulations', 'all'],
    supportedTopics: ['employment', 'contract', 'property', 'corporate', 'family', 'criminal'],
  });
}
