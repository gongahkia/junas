import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/session';
import Anthropic from '@anthropic-ai/sdk';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  try {
    // Get API key from session
    const session = await getSession();
    const apiKey = session.apiKeys?.claude;

    if (!apiKey) {
      return NextResponse.json(
        { error: 'Claude API key not configured. Please add it in Settings.' },
        { status: 401 }
      );
    }

    // Parse request body
    const body = await request.json();
    const { messages, model = 'claude-3-5-sonnet-20241022', temperature = 0.7, maxTokens = 4096, stream = false } = body;

    // Initialize Anthropic client
    const client = new Anthropic({
      apiKey,
    });

    // Make request to Claude API
    if (stream) {
      // For streaming responses
      const stream = await client.messages.create({
        model,
        max_tokens: maxTokens,
        temperature,
        messages,
        stream: true,
      });

      const encoder = new TextEncoder();
      const readable = new ReadableStream({
        async start(controller) {
          try {
            for await (const chunk of stream) {
              if (chunk.type === 'content_block_delta' && chunk.delta.type === 'text_delta') {
                const data = JSON.stringify({ content: chunk.delta.text }) + '\n';
                controller.enqueue(encoder.encode(data));
              }
            }
            controller.close();
          } catch (error) {
            console.error('Streaming error:', error);
            controller.error(error);
          }
        },
      });

      return new NextResponse(readable, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    } else {
      // For non-streaming responses
      const response = await client.messages.create({
        model,
        max_tokens: maxTokens,
        temperature,
        messages,
      });

      return NextResponse.json({
        content: response.content[0].type === 'text' ? response.content[0].text : '',
        model: response.model,
        usage: {
          inputTokens: response.usage.input_tokens,
          outputTokens: response.usage.output_tokens,
        },
      });
    }
  } catch (error: any) {
    console.error('Claude API error:', error);
    return NextResponse.json(
      {
        error: error.message || 'Failed to communicate with Claude API',
        code: error.status || 500,
      },
      { status: error.status || 500 }
    );
  }
}
