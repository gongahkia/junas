import { NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const session = await getSession();
    const keys = session.apiKeys || {};

    const providers = [
      { id: 'gemini', url: 'https://generativelanguage.googleapis.com' },
      { id: 'openai', url: 'https://api.openai.com' },
      { id: 'claude', url: 'https://api.anthropic.com' },
      { id: 'ollama', url: keys.ollama || 'http://localhost:11434' },
      { id: 'lmstudio', url: keys.lmstudio || 'http://localhost:1234/v1' },
    ];

    const results = await Promise.all(
      providers.map(async (p) => {
        const isLocal = p.id === 'ollama' || p.id === 'lmstudio';
        const hasKey = !!keys[p.id as keyof typeof keys];

        if (!hasKey && !isLocal) {
          return { id: p.id, status: 'unconfigured' };
        }

        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 3000);
          
          let targetUrl = p.url;
          if (p.id === 'ollama') targetUrl = `${p.url.replace(/\/$/, '')}/api/tags`;
          if (p.id === 'lmstudio') targetUrl = `${p.url.replace(/\/$/, '')}/models`;

          // We use a simple fetch. If it doesn't throw a network error, it's "reachable"
          // We don't care about 401/404/405 for health checks as long as the server responds
          const response = await fetch(targetUrl, {
            method: 'GET',
            signal: controller.signal,
            headers: {
              'User-Agent': 'Junas-Health-Check'
            }
          }).catch(async () => {
              // Try again with just the base domain if specific path fails
              return await fetch(p.url, { method: 'HEAD', signal: controller.signal });
          });

          clearTimeout(timeoutId);
          return { id: p.id, status: 'online' };
        } catch (e) {
          return { id: p.id, status: 'offline' };
        }
      })
    );

    const statusMap = results.reduce((acc, curr) => {
      acc[curr.id] = curr.status;
      return acc;
    }, {} as Record<string, string>);

    return NextResponse.json(statusMap);
  } catch (error) {
    console.error('Health check error:', error);
    return NextResponse.json({ error: 'Failed to perform health check' }, { status: 500 });
  }
}
