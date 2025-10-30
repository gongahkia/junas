'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Message } from '@/types/chat';
import { FileDown, FileJson, FileText, FileType } from 'lucide-react';
import { exportToPDF } from '@/lib/pdf-export';

interface ExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  messages: Message[];
}

type ExportFormat = 'json' | 'markdown' | 'txt' | 'pdf';

export function ExportDialog({ isOpen, onClose, messages }: ExportDialogProps) {
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('pdf');

  const exportAsJSON = () => {
    const data = {
      __junas_export__: true,
      __junas_version__: '1.0.0',
      __junas_signature__: 'JUNAS_LEGAL_AI_EXPORT',
      metadata: {
        exportDate: new Date().toISOString(),
        messageCount: messages.length,
        application: 'Junas - Legal AI Assistant',
      },
      messages: messages.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
      })),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json;charset=utf-8'
    });
    downloadFile(blob, `junas-conversation-${Date.now()}.json`);
  };

  const exportAsMarkdown = () => {
    const lines: string[] = [];
    lines.push('<!-- __JUNAS_EXPORT__:true __JUNAS_VERSION__:1.0.0 __JUNAS_SIGNATURE__:JUNAS_LEGAL_AI_EXPORT -->\n');
    lines.push('# Junas Conversation\n');
    lines.push(`**Generated:** ${new Date().toLocaleString()}\n`);
    lines.push(`**Total Messages:** ${messages.length}\n`);
    lines.push('---\n');

    for (const m of messages) {
      lines.push(`## ${m.role === 'user' ? 'User' : 'Assistant'}\n`);
      lines.push(m.content);
      lines.push('\n');
    }

    const blob = new Blob([lines.join('\n')], {
      type: 'text/markdown;charset=utf-8'
    });
    downloadFile(blob, `junas-conversation-${Date.now()}.md`);
  };

  const exportAsText = () => {
    const lines: string[] = [];
    lines.push('__JUNAS_EXPORT__:true __JUNAS_VERSION__:1.0.0 __JUNAS_SIGNATURE__:JUNAS_LEGAL_AI_EXPORT');
    lines.push('JUNAS CONVERSATION');
    lines.push('='.repeat(50));
    lines.push(`Generated: ${new Date().toLocaleString()}`);
    lines.push(`Total Messages: ${messages.length}`);
    lines.push('='.repeat(50));
    lines.push('');

    for (let i = 0; i < messages.length; i++) {
      const m = messages[i];
      lines.push(`[${i + 1}] ${m.role.toUpperCase()}`);
      lines.push('-'.repeat(50));
      lines.push(m.content);
      lines.push('');
    }

    const blob = new Blob([lines.join('\n')], {
      type: 'text/plain;charset=utf-8'
    });
    downloadFile(blob, `junas-conversation-${Date.now()}.txt`);
  };

  const downloadFile = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const exportAsPDF = () => {
    exportToPDF(messages, `junas-conversation-${Date.now()}`);
  };

  const handleExport = () => {
    switch (selectedFormat) {
      case 'json':
        exportAsJSON();
        break;
      case 'markdown':
        exportAsMarkdown();
        break;
      case 'txt':
        exportAsText();
        break;
      case 'pdf':
        exportAsPDF();
        break;
    }
    onClose();
  };

  const formatOptions = [
    {
      value: 'pdf' as ExportFormat,
      label: 'PDF',
      description: 'Professional document format (recommended)',
      icon: FileDown,
    },
    {
      value: 'json' as ExportFormat,
      label: 'JSON',
      description: 'Structured data format with all metadata',
      icon: FileJson,
    },
    {
      value: 'markdown' as ExportFormat,
      label: 'Markdown',
      description: 'Formatted text with styling',
      icon: FileText,
    },
    {
      value: 'txt' as ExportFormat,
      label: 'Plain Text',
      description: 'Simple text file',
      icon: FileType,
    },
  ];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center space-x-2">
            <FileDown className="h-5 w-5" />
            <span>Export Conversation</span>
          </DialogTitle>
          <DialogDescription>
            Choose a format to export your conversation
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-4">
          {formatOptions.map(option => {
            const Icon = option.icon;
            return (
              <button
                key={option.value}
                onClick={() => setSelectedFormat(option.value)}
                className={`w-full flex items-start space-x-3 p-4 rounded-lg border-2 transition-all ${
                  selectedFormat === option.value
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
                <div className="text-left flex-1">
                  <div className="font-medium">{option.label}</div>
                  <div className="text-sm text-muted-foreground">
                    {option.description}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleExport}>
            Export as {selectedFormat.toUpperCase()}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
