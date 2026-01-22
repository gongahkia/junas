import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    let url = body.url;

    if (!url) {
      return NextResponse.json(
        { error: 'URL is required' },
        { status: 400 }
      );
    }

    // Normalize URL: append https:// if missing protocol
    if (!/^https?:\/\//i.test(url)) {
        url = 'https://' + url;
    }

    try {
      new URL(url);
    } catch (e) {
      return NextResponse.json(
        { error: 'Invalid URL format' },
        { status: 400 }
      );
    }

    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; Junas/1.0; +http://localhost)',
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch URL: ${response.status} ${response.statusText}` },
        { status: response.status }
      );
    }

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('text/html') && !contentType.includes('text/plain')) {
       return NextResponse.json(
        { error: 'URL must point to a text or HTML resource' },
        { status: 400 }
      );
    }

    const html = await response.text();
    let textContent = html;

    if (contentType.includes('text/html')) {
        // Simple HTML to text conversion
        // 1. Remove scripts and styles
        textContent = textContent.replace(/<script\b[^>]*>([\s\S]*?)<\/script>/gim, '');
        textContent = textContent.replace(/<style\b[^>]*>([\s\S]*?)<\/style>/gim, '');
        
        // 2. Replace breaks and paragraphs with newlines
        textContent = textContent.replace(/<br\s*\/?>/gi, '\n');
        textContent = textContent.replace(/<\/p>/gi, '\n\n');
        textContent = textContent.replace(/<\/div>/gi, '\n');
        
        // 3. Strip remaining tags
        textContent = textContent.replace(/<[^>]+>/g, '');
        
        // 4. Decode HTML entities (basic ones)
        textContent = textContent
            .replace(/&nbsp;/g, ' ')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"');
            
        // 5. Clean up whitespace
        textContent = textContent.replace(/\n\s+\n/g, '\n\n').trim();
    }

    // Limit content length to avoid context window overflow (e.g., 20k chars)
    if (textContent.length > 20000) {
        textContent = textContent.slice(0, 20000) + '... (content truncated)';
    }

    return NextResponse.json({ content: textContent });

  } catch (error: any) {
    console.error('Fetch URL error:', error);
    return NextResponse.json(
      { error: `Internal server error: ${error.message}` },
      { status: 500 }
    );
  }
}
