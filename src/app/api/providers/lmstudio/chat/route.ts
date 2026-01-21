import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  try {
    // Get Base URL from session (stored in apiKeys.lmstudio)
    const session = await getSession();
    // Default to localhost:1234/v1 for LM Studio
    const baseUrl = session.apiKeys?.lmstudio || 'http://localhost:1234/v1';

    // Parse request body
    const body = await request.json();
    const { messages, model = 'local-model', temperature = 0.7, stream = false } = body;

    // LM Studio uses OpenAI-compatible format
    const payload = {
      model,
      messages,
      temperature,
      stream,
      max_tokens: -1, // -1 often means auto/unlimited in LM Studio/OpenAI compatible local servers
    };

    // Make request to LM Studio API (OpenAI compatible endpoint)
    // Note: ensure baseUrl includes /v1 if LM Studio is running on default port, usually http://localhost:1234/v1
    const endpoint = baseUrl.endsWith('/chat/completions') 
        ? baseUrl 
        : `${baseUrl.replace(///$/, '')}/chat/completions`;

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
        throw new Error(`LM Studio API returned ${response.status}: ${response.statusText}`);
    }

    if (stream) {
      // For streaming responses
      const reader = response.body?.getReader();
      const encoder = new TextEncoder();
      const decoder = new TextDecoder();

      const readable = new ReadableStream({
        async start(controller) {
          try {
            if (reader) {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                // OpenAI compatible streams send "data: { ... }" lines
                
                const lines = chunk.split('\n').filter(l => l.trim());
                for (const line of lines) {
                   if (line.trim() === 'data: [DONE]') continue;
                   if (line.startsWith('data: ')) {
                       try {
                           const json = JSON.parse(line.slice(6));
                           const content = json.choices[0]?.delta?.content;
                           if (content) {
                               const data = JSON.stringify({ content }) + '\n';
                               controller.enqueue(encoder.encode(data));
                           }
                       } catch (e) {
                           // Skip invalid
                       }
                   }
                }
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
      const result = await response.json();
      return NextResponse.json({
        content: result.choices[0]?.message?.content || '',
        model: result.model,
        usage: {
            totalTokens: result.usage?.total_tokens || 0
        },
      });
    }
  } catch (error: any) {
    console.error('LM Studio API error:', error);
    return NextResponse.json(
      {
        error: error.message || 'Failed to communicate with LM Studio API',
        code: 500,
      },
      { status: 500 }
    );
  }
}
