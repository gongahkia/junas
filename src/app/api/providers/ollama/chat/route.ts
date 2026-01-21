import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  try {
    // Get Base URL from session (stored in apiKeys.ollama)
    const session = await getSession();
    const baseUrl = session.apiKeys?.ollama || 'http://localhost:11434';

    // Parse request body
    const body = await request.json();
    const { messages, model = 'llama3', temperature = 0.7, stream = false } = body;

    // Remove system messages for models that might not support them strictly,
    // or format them. Ollama supports 'system' role usually.
    // However, some older models/versions might differ. 
    // We'll pass them as is for now.

    const ollamaPayload = {
      model,
      messages,
      temperature,
      stream,
      options: {
        temperature,
        // map maxTokens if needed, Ollama uses num_predict or similar in options
      }
    };

    // Make request to Ollama API
    const response = await fetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ollamaPayload),
    });

    if (!response.ok) {
        throw new Error(`Ollama API returned ${response.status}: ${response.statusText}`);
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
                // Ollama sends JSON objects, one per line (or multiple)
                // We need to parse them and extract 'message.content'
                
                // Note: fetch streaming might split JSONs. 
                // A robust parser would buffer. 
                // For simplicity here, assuming reasonable chunks or line-delimited.
                // Ollama output is usually one JSON object per line/chunk.
                
                const lines = chunk.split('\n').filter(l => l.trim());
                for (const line of lines) {
                   try {
                       const json = JSON.parse(line);
                       const content = json.message?.content;
                       if (content) {
                           const data = JSON.stringify({ content }) + '\n';
                           controller.enqueue(encoder.encode(data));
                       }
                       if (json.done) {
                           // Done
                       }
                   } catch (e) {
                       // Incomplete JSON or error, skip for now
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
        content: result.message?.content || '',
        model: result.model,
        usage: {
            // Ollama might provide these in 'eval_count' etc
            totalTokens: result.eval_count || 0
        },
      });
    }
  } catch (error: any) {
    console.error('Ollama API error:', error);
    return NextResponse.json(
      {
        error: error.message || 'Failed to communicate with Ollama API',
        code: 500,
      },
      { status: 500 }
    );
  }
}
