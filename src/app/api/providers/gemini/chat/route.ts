import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/session';
import { GoogleGenerativeAI } from '@google/generative-ai';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  try {
    // Get API key from session
    const session = await getSession();
    const apiKey = session.apiKeys?.gemini;

    if (!apiKey) {
      return NextResponse.json(
        { error: 'Gemini API key not configured. Please add it in Settings.' },
        { status: 401 }
      );
    }

    // Parse request body
    const body = await request.json();
    const { messages, model = 'gemini-2.0-flash-exp', temperature = 0.7, maxTokens = 4096, stream = false } = body;

    // Initialize Gemini client
    const genAI = new GoogleGenerativeAI(apiKey);
    const modelInstance = genAI.getGenerativeModel({
      model,
      generationConfig: {
        temperature,
        maxOutputTokens: maxTokens,
      },
    });

    // Convert messages to Gemini format
    const contents = messages.map((msg: any) => ({
      role: msg.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: msg.content }],
    }));

    // Make request to Gemini API
    if (stream) {
      // For streaming responses
      const result = await modelInstance.generateContentStream({
        contents,
      });

      const encoder = new TextEncoder();
      const readable = new ReadableStream({
        async start(controller) {
          let isClosed = false;

          const safeEnqueue = (data: Uint8Array) => {
            if (!isClosed) {
              try {
                controller.enqueue(data);
              } catch (error) {
                isClosed = true;
              }
            }
          };

          const safeClose = () => {
            if (!isClosed) {
              try {
                controller.close();
                isClosed = true;
              } catch (error) {
                // Already closed, ignore
              }
            }
          };

          try {
            for await (const chunk of result.stream) {
              if (isClosed) break; // Stop if stream was closed

              const text = chunk.text();
              if (text) {
                const data = JSON.stringify({ content: text }) + '\n';
                safeEnqueue(encoder.encode(data));
              }
            }
            safeClose();
          } catch (error) {
            console.error('Streaming error:', error);
            if (!isClosed) {
              controller.error(error);
              isClosed = true;
            }
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
      const result = await modelInstance.generateContent({
        contents,
      });

      const response = await result.response;
      const text = response.text();

      return NextResponse.json({
        content: text,
        model,
        usage: {
          inputTokens: 0, // Gemini doesn't provide token counts in free tier
          outputTokens: 0,
        },
      });
    }
  } catch (error: any) {
    console.error('Gemini API error:', error);
    return NextResponse.json(
      {
        error: error.message || 'Failed to communicate with Gemini API',
        code: error.status || 500,
      },
      { status: error.status || 500 }
    );
  }
}
