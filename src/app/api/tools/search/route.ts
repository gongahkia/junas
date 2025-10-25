import { NextRequest, NextResponse } from 'next/server';
import { LegalSearchEngine } from '@/lib/tools/legal-search';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { query, type, topic } = body;

    if (!query || typeof query !== 'string') {
      return NextResponse.json(
        { error: 'Query is required' },
        { status: 400 }
      );
    }

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
    console.error('Legal search API error:', error);
    
    return NextResponse.json(
      { 
        error: error.message || 'Legal search failed',
        success: false,
      },
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
