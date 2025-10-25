import { NextRequest, NextResponse } from 'next/server';
import { ProviderFactory } from '@/lib/ai/provider-factory';
import { ChatState, Message } from '@/types/chat';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { messages, provider, apiKey, tools, options } = body;

    if (!messages || !Array.isArray(messages)) {
      return NextResponse.json(
        { error: 'Messages array is required' },
        { status: 400 }
      );
    }

    if (!provider || !apiKey) {
      return NextResponse.json(
        { error: 'Provider and API key are required' },
        { status: 400 }
      );
    }

    // Create provider instance
    const providerInstance = ProviderFactory.createProvider(provider, {
      name: provider,
      displayName: provider,
      apiKey,
      model: options?.model || 'default',
      temperature: options?.temperature || 0.7,
      maxTokens: options?.maxTokens || 4000,
      enabled: true,
    });

    // Generate response
    const response = await providerInstance.generateResponse(
      messages,
      tools,
      options
    );

    return NextResponse.json({
      content: response.content,
      usage: response.usage,
      model: response.model,
      finishReason: response.finishReason,
    });

  } catch (error: any) {
    console.error('Chat API error:', error);
    
    return NextResponse.json(
      { 
        error: error.message || 'An error occurred while processing your request',
        code: error.code || 'UNKNOWN_ERROR',
        retryable: error.retryable || false,
      },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    message: 'Chat API endpoint',
    supportedProviders: ProviderFactory.getAvailableProviders(),
  });
}
