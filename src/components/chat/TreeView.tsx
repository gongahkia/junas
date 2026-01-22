'use client';

import { useEffect, useState, useRef } from 'react';
import { Message } from '@/types/chat';
import { generateDotTree } from '@/lib/chat-tree';

interface TreeViewProps {
  nodeMap: Record<string, Message>;
  currentLeafId?: string;
  onSelectNode: (nodeId: string) => void;
}

export function TreeView({ nodeMap, currentLeafId, onSelectNode }: TreeViewProps) {
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;

    const renderDiagram = async () => {
      try {
        setIsLoading(true);
        setError('');

        const isDarkMode = document.documentElement.classList.contains('dark');
        const chart = generateDotTree(nodeMap, currentLeafId, isDarkMode);

        // Dynamically import viz.js
        const { instance } = await import('@viz-js/viz');
        const viz = await instance();

        const result = viz.renderString(chart, { format: 'svg' });

        if (mounted) {
          setSvg(result);
          setIsLoading(false);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to render diagram');
          setIsLoading(false);
        }
      }
    };

    renderDiagram();

    return () => {
      mounted = false;
    };
  }, [nodeMap, currentLeafId]);

  // Attach click listeners
  useEffect(() => {
    if (!containerRef.current || !svg) return;

    const nodes = containerRef.current.querySelectorAll('.node');
    const handlers: { element: Element, handler: () => void }[] = [];

    nodes.forEach(node => {
        const id = node.id.replace('node_', '');
        // Apply cursor pointer
        (node as HTMLElement).style.cursor = 'pointer';
        
        const handler = () => {
            onSelectNode(id);
        };
        
        node.addEventListener('click', handler);
        handlers.push({ element: node, handler });
    });

    return () => {
        handlers.forEach(({ element, handler }) => {
            element.removeEventListener('click', handler);
        });
    };
  }, [svg, onSelectNode]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden p-4">
        <div className="flex-1 overflow-auto bg-muted/10 rounded-md p-4 flex items-center justify-center min-h-[300px] border border-muted-foreground/10">
            {isLoading ? (
                <div className="text-sm text-muted-foreground animate-pulse">Generating tree view...</div>
            ) : error ? (
                <div className="text-sm text-red-500">{error}</div>
            ) : (
                <div 
                    ref={containerRef}
                    dangerouslySetInnerHTML={{ __html: svg }} 
                    className="w-full h-full flex justify-center"
                />
            )}
        </div>
        
        <div className="mt-2 text-center text-[10px] text-muted-foreground">
            Click on any node to jump to that point in the conversation.
        </div>
    </div>
  );
}
