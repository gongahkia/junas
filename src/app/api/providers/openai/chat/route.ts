import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/session';
import OpenAI from 'openai';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  try {
    // Get API key from session
    const session = await getSession();
    const apiKey = session.apiKeys?.openai;

    if (!apiKey) {
      return NextResponse.json(
        { error: 'OpenAI API key not configured. Please add it in Settings.' },
        { status: 401 }
      );
    }

    // Parse request body
    const body = await request.json();
    const { messages, model = 'gpt-4o', temperature = 0.7, maxTokens = 4096, stream = false } = body;

    // Initialize OpenAI client (no dangerouslyAllowBrowser needed!)
    const client = new OpenAI({
      apiKey,
    });

    // Make request to OpenAI API
    if (stream) {
      // For streaming responses
      const stream = await client.chat.completions.create({
        model,
        messages,
        temperature,
        max_tokens: maxTokens,
        stream: true,
      });

      const encoder = new TextEncoder();
      const readable = new ReadableStream({
        async start(controller) {
          try {
            for await (const chunk of stream) {
              const content = chunk.choices[0]?.delta?.content;
              if (content) {
                const data = JSON.stringify({ content }) + '\n';
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
      const response = await client.chat.completions.create({
        model,
        messages,
        temperature,
        max_tokens: maxTokens,
      });

      return NextResponse.json({
        content: response.choices[0]?.message?.content || '',
        model: response.model,
        usage: {
          inputTokens: response.usage?.prompt_tokens || 0,
          outputTokens: response.usage?.completion_tokens || 0,
        },
      });
    }
  } catch (error: any) {
    console.error('OpenAI API error:', error);
    return NextResponse.json(
      {
        error: error.message || 'Failed to communicate with OpenAI API',
        code: error.status || 500,
      },
      { status: error.status || 500 }
    );
  }
}
