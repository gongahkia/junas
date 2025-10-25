'use client';

import { Button } from '@/components/ui/button';
import { Download } from 'lucide-react';
import { Message } from '@/types/chat';

function buildMarkdown(messages: Message[]): string {
  const lines: string[] = [];
  lines.push(`# Junas Conversation\n`);
  lines.push(`Generated: ${new Date().toISOString()}\n`);
  for (const m of messages) {
    lines.push(`## ${m.role.toUpperCase()}\n`);
    lines.push(m.content);
    lines.push('');
  }
  return lines.join('\n');
}

export function ExportButton({ messages }: { messages: Message[] }) {
  const handleExport = () => {
    const md = buildMarkdown(messages);
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `junas-conversation-${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <Button variant="ghost" size="sm" onClick={handleExport} className="h-9 px-3">
      <Download className="h-4 w-4 mr-2" />
      Export
    </Button>
  );
}


