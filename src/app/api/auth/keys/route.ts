import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { gemini, openai, claude } = body;

    // Validate that at least one key is provided
    if (!gemini && !openai && !claude) {
      return NextResponse.json(
        { error: 'At least one API key must be provided' },
        { status: 400 }
      );
    }

    // Get session and store keys
    const session = await getSession();
    session.apiKeys = {
      ...(gemini && { gemini }),
      ...(openai && { openai }),
      ...(claude && { claude }),
    };
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

    // Return which providers have keys configured (without exposing the keys)
    const providers = {
      gemini: !!session.apiKeys?.gemini,
      openai: !!session.apiKeys?.openai,
      claude: !!session.apiKeys?.claude,
    };

    return NextResponse.json({
      configured: providers,
      hasAnyKey: Object.values(providers).some(Boolean),
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
