import { NextRequest, NextResponse } from 'next/server';
import { ContractAnalyzer } from '@/lib/tools/contract-analyzer';
import { calculateRiskLevel, formatErrorResponse } from '@/lib/api-utils';
import { AnalyzeRequestSchema, validateData } from '@/lib/validation';
import { sanitizePlainText } from '@/lib/sanitize';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate input with Zod schema
    const validation = validateData(AnalyzeRequestSchema, body);
    if (!validation.success) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      );
    }

    // Sanitize text input
    const text = sanitizePlainText(validation.data.text);

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
