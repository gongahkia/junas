'use client';

import { useEffect, useRef, useState } from 'react';

interface MermaidDiagramProps {
  chart: string;
}

// Track if mermaid has been initialized globally
let mermaidInitialized = false;

export function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;

    const renderDiagram = async () => {
      if (!chart) return;

      try {
        setIsLoading(true);
        setError('');

        // Dynamically import mermaid to avoid SSR issues
        const mermaid = (await import('mermaid')).default;

        // Initialize mermaid only once
        if (!mermaidInitialized) {
          mermaid.initialize({
            startOnLoad: false,
            theme: 'default',
            securityLevel: 'loose',
            fontFamily: 'var(--font-geist-sans), sans-serif',
            flowchart: {
              useMaxWidth: true,
              htmlLabels: true,
              curve: 'basis',
            },
            themeVariables: {
              fontSize: '14px',
            },
          });
          mermaidInitialized = true;
        }

        // Generate unique ID for this diagram
        const id = `mermaid-${Date.now()}-${Math.random().toString(36).substring(7)}`;

        // Render the diagram
        const { svg: renderedSvg } = await mermaid.render(id, chart);

        if (mounted) {
          setSvg(renderedSvg);
          setIsLoading(false);
        }
      } catch (err) {
        console.error('Mermaid rendering error:', err);
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to render diagram');
          setIsLoading(false);
        }
      }
    };

    renderDiagram();

    // Cleanup function
    return () => {
      mounted = false;
    };
  }, [chart]);

  if (isLoading) {
    return (
      <div className="my-4 flex items-center justify-center rounded-lg border bg-card p-8">
        <div className="text-sm text-muted-foreground animate-pulse">
          Rendering diagram...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="my-4 rounded-lg border border-destructive bg-destructive/10 p-4">
        <p className="text-sm font-medium text-destructive">
          Failed to render diagram
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{error}</p>
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
            Show diagram code
          </summary>
          <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 text-xs">
            <code>{chart}</code>
          </pre>
        </details>
      </div>
    );
  }

  return (
    <div
      className="my-4 flex items-center justify-center overflow-x-auto rounded-lg border bg-card p-4"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
