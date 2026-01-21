import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { gemini, openai, claude, ollama } = body;

    // Get session and merge with existing keys
    const session = await getSession();

    // Start with existing keys or empty object
    const existingKeys = session.apiKeys || {};

    // Update only the keys that were provided (preserve existing ones)
    session.apiKeys = {
      ...existingKeys,
      ...(gemini !== undefined && { gemini }),
      ...(openai !== undefined && { openai }),
      ...(claude !== undefined && { claude }),
      ...(ollama !== undefined && { ollama }),
    };

    // Remove empty keys
    if (gemini === '') delete session.apiKeys.gemini;
    if (openai === '') delete session.apiKeys.openai;
    if (claude === '') delete session.apiKeys.claude;
    if (ollama === '') delete session.apiKeys.ollama;

    session.createdAt = Date.now();
    await session.save();

    return NextResponse.json({
      success: true,
      providers: Object.keys(session.apiKeys),
    });
  } catch (error) {
    console.error('Error storing API keys:', error);
    return NextResponse.json(
      { error: 'Failed to store API keys' },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    const session = await getSession();

    // Return which providers have keys configured
    const configured = {
      gemini: !!session.apiKeys?.gemini,
      openai: !!session.apiKeys?.openai,
      claude: !!session.apiKeys?.claude,
      ollama: !!session.apiKeys?.ollama,
    };

    // Return the actual keys for populating the UI
    // These are already stored securely in the user's session
    const keys = {
      gemini: session.apiKeys?.gemini || '',
      openai: session.apiKeys?.openai || '',
      claude: session.apiKeys?.claude || '',
      ollama: session.apiKeys?.ollama || '',
    };

    return NextResponse.json({
      configured,
      keys,
      hasAnyKey: Object.values(configured).some(Boolean),
    });
  } catch (error) {
    console.error('Error retrieving API key status:', error);
    return NextResponse.json(
      { error: 'Failed to retrieve API key status' },
      { status: 500 }
    );
  }
}

export async function DELETE() {
  try {
    const session = await getSession();
    session.destroy();

    return NextResponse.json({
      success: true,
      message: 'API keys cleared',
    });
  } catch (error) {
    console.error('Error clearing API keys:', error);
    return NextResponse.json(
      { error: 'Failed to clear API keys' },
      { status: 500 }
    );
  }
}
