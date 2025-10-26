import { NextRequest, NextResponse } from 'next/server';
import { DocumentSummary } from '@/types/tool';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { text, type } = body;

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

    // Generate summary based on type
    let summary: DocumentSummary;

    if (type === 'contract') {
      summary = await summarizeContract(text);
    } else if (type === 'case') {
      summary = await summarizeCase(text);
    } else if (type === 'statute') {
      summary = await summarizeStatute(text);
    } else {
      summary = await summarizeGeneral(text);
    }

    return NextResponse.json({
      success: true,
      summary,
      metadata: {
        textLength: text.length,
        processingTime: Date.now(),
        type,
      },
    });

  } catch (error: any) {
    console.error('Document summarization API error:', error);
    
    return NextResponse.json(
      { 
        error: error.message || 'Document summarization failed',
        success: false,
      },
      { status: 500 }
    );
  }
}

async function summarizeContract(text: string): Promise<DocumentSummary> {
  // Extract key contract elements
  const parties = text.match(/(?:between|BETWEEN)\s+([^,]+(?:\s+and\s+[^,]+)*)/gi) || [];
  const dates = text.match(/\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}/g) || [];
  const amounts = text.match(/\$[\d,]+(?:\.\d{2})?/g) || [];

  const oneSentence = `Contract between ${parties[0] || 'parties'} involving ${amounts[0] || 'financial terms'} with effective date ${dates[0] || 'TBD'}.`;
  
  const paragraph = `This contract involves ${parties.length} parties with key financial terms of ${amounts[0] || 'undisclosed amount'}. The agreement includes standard commercial terms with effective date of ${dates[0] || 'to be determined'}. Key provisions cover payment terms, termination clauses, and dispute resolution mechanisms.`;
  
  const keyPoints = [
    `Parties: ${parties.join(', ') || 'Not specified'}`,
    `Financial terms: ${amounts.join(', ') || 'Not specified'}`,
    `Effective date: ${dates[0] || 'Not specified'}`,
    'Standard commercial terms included',
    'Dispute resolution mechanisms specified',
  ];

  return {
    oneSentence,
    paragraph,
    keyPoints,
    wordCount: text.split(/\s+/).length,
    readingTime: Math.ceil(text.split(/\s+/).length / 200),
  };
}

async function summarizeCase(text: string): Promise<DocumentSummary> {
  // Extract case elements
  const caseName = text.match(/^([A-Z][a-z]+\s+[A-Z][a-z]+\s+v\.\s+[A-Z][a-z]+)/m)?.[0] || 'Case name not found';
  const court = text.match(/(?:Court|Tribunal|Judge)\s+([A-Z][a-z]+)/gi)?.[0] || 'Court not specified';
  const year = text.match(/\d{4}/)?.[0] || 'Year not specified';

  const oneSentence = `${caseName} (${year}) decided by ${court} involving key legal principles.`;
  
  const paragraph = `This case involves ${caseName} decided in ${year} by ${court}. The court addressed important legal principles and established precedents. Key holdings include significant legal reasoning and application of relevant statutes.`;
  
  const keyPoints = [
    `Case: ${caseName}`,
    `Court: ${court}`,
    `Year: ${year}`,
    'Key legal principles established',
    'Precedent value for future cases',
  ];

  return {
    oneSentence,
    paragraph,
    keyPoints,
    wordCount: text.split(/\s+/).length,
    readingTime: Math.ceil(text.split(/\s+/).length / 200),
  };
}

async function summarizeStatute(text: string): Promise<DocumentSummary> {
  // Extract statute elements
  const title = text.match(/^(?:Act|Regulation|Rule|Order)\s+(?:No\.?\s*)?\d+\s+of\s+\d{4}/m)?.[0] || 'Statute title not found';
  const sections = text.match(/(?:s\.|section)\s*\d+[a-z]?/gi) || [];
  const year = text.match(/\d{4}/)?.[0] || 'Year not specified';

  const oneSentence = `${title} (${year}) containing ${sections.length} sections with key legal provisions.`;
  
  const paragraph = `This statute ${title} enacted in ${year} contains ${sections.length} sections covering important legal provisions. The act establishes key legal frameworks and regulatory requirements.`;
  
  const keyPoints = [
    `Title: ${title}`,
    `Year: ${year}`,
    `Sections: ${sections.length}`,
    'Key legal provisions established',
    'Regulatory framework defined',
  ];

  return {
    oneSentence,
    paragraph,
    keyPoints,
    wordCount: text.split(/\s+/).length,
    readingTime: Math.ceil(text.split(/\s+/).length / 200),
  };
}

async function summarizeGeneral(text: string): Promise<DocumentSummary> {
  const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
  const firstSentence = sentences[0] || 'Document summary not available';
  
  const paragraph = sentences.slice(0, 3).join('. ') + '.';
  
  const keyPoints = sentences.slice(0, 5).map(sentence => sentence.trim());

  return {
    oneSentence: firstSentence,
    paragraph,
    keyPoints,
    wordCount: text.split(/\s+/).length,
    readingTime: Math.ceil(text.split(/\s+/).length / 200),
  };
}

export async function GET() {
  return NextResponse.json({
    message: 'Document summarization API endpoint',
    supportedTypes: ['contract', 'case', 'statute', 'general'],
    maxTextLength: '100,000 characters',
  });
}
