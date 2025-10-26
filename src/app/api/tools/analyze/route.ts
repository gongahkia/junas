import { NextRequest, NextResponse } from 'next/server';
import { ContractAnalyzer } from '@/lib/tools/contract-analyzer';

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

    // Analyze the contract
    const analysis = await ContractAnalyzer.analyzeContract(text);

    return NextResponse.json({
      success: true,
      analysis,
      metadata: {
        textLength: text.length,
        processingTime: Date.now(),
        riskLevel: calculateRiskLevel(analysis.riskFlags),
      },
    });

  } catch (error: any) {
    console.error('Contract analysis API error:', error);
    
    return NextResponse.json(
      { 
        error: error.message || 'Contract analysis failed',
        success: false,
      },
      { status: 500 }
    );
  }
}

function calculateRiskLevel(riskFlags: any[]): string {
  const highRiskCount = riskFlags.filter(flag => flag.severity === 'high').length;
  const mediumRiskCount = riskFlags.filter(flag => flag.severity === 'medium').length;
  
  if (highRiskCount > 0) return 'high';
  if (mediumRiskCount > 2) return 'medium';
  if (riskFlags.length > 0) return 'low';
  return 'none';
}

export async function GET() {
  return NextResponse.json({
    message: 'Contract analysis API endpoint',
    maxTextLength: '100,000 characters',
    analysisTypes: ['parties', 'dates', 'terms', 'risks', 'liability', 'dispute resolution'],
  });
}
