import { NextRequest, NextResponse } from 'next/server';
import { ContractAnalyzer } from '@/lib/tools/contract-analyzer';
import { validateTextInput, calculateRiskLevel, formatErrorResponse } from '@/lib/api-utils';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { text } = body;

    // Validate input
    const validation = validateTextInput(text, 100000);
    if (!validation.valid) {
      return NextResponse.json(
        { error: validation.error },
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
    return NextResponse.json(
      formatErrorResponse(error, 'Contract analysis'),
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    message: 'Contract analysis API endpoint',
    maxTextLength: '100,000 characters',
    analysisTypes: ['parties', 'dates', 'terms', 'risks', 'liability', 'dispute resolution'],
  });
}
