import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { query } = body;

    if (!query) {
      return NextResponse.json(
        { error: 'Search query is required' },
        { status: 400 }
      );
    }

    // This is a placeholder for a real search API (e.g., Serper, Tavily, Google Custom Search)
    // Since we don't have a key, we'll simulate results or use a free/public service if available.
    // For now, we'll provide a mock implementation that suggests using a real API.

    const SERPER_API_KEY = process.env.SERPER_API_KEY;

    if (SERPER_API_KEY) {
      const response = await fetch('https://google.serper.dev/search', {
        method: 'POST',
        headers: {
          'X-API-KEY': SERPER_API_KEY,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ q: query }),
      });

      if (response.ok) {
        const data = await response.json();
        const results = data.organic?.map((item: any) => ({
          title: item.title,
          link: item.link,
          snippet: item.snippet,
        })) || [];
        return NextResponse.json({ results });
      }
    }

    // Fallback: Mock results for demonstration if no API key is provided
    // In a real production app, you'd want a real API.
    return NextResponse.json({
      results: [
        {
          title: `Search results for: ${query}`,
          link: `https://www.google.com/search?q=${encodeURIComponent(query)}`,
          snippet: "To enable real web search results, please add a SERPER_API_KEY to your environment variables. This is a placeholder result showing where the search output would appear.",
        },
        {
          title: "DuckDuckGo Search",
          link: `https://duckduckgo.com/?q=${encodeURIComponent(query)}`,
          snippet: "You can also search directly on DuckDuckGo for privacy-focused results.",
        }
      ],
      warning: "No search API key configured. Showing placeholder results."
    });

  } catch (error: any) {
    console.error('Web search error:', error);
    return NextResponse.json(
      { error: `Internal server error: ${error.message}` },
      { status: 500 }
    );
  }
}
