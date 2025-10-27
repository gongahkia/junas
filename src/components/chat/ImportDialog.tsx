'use client';

import { useState, useRef } from 'react';
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
import { Upload, FileJson, FileText, FileType } from 'lucide-react';
import { useToast } from '@/components/ui/toast';

interface ImportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onImport: (messages: Message[]) => void;
}

type ImportFormat = 'json' | 'markdown' | 'txt';

export function ImportDialog({ isOpen, onClose, onImport }: ImportDialogProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addToast } = useToast();

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsProcessing(true);

    try {
      const text = await file.text();
      const messages = parseImportedFile(text, file.name);

      if (messages.length === 0) {
        throw new Error('No messages found in the imported file');
      }

      onImport(messages);
      addToast({
        type: 'success',
        title: 'Import Successful',
        description: `Imported ${messages.length} messages`,
        duration: 3000,
      });
      onClose();
    } catch (error: any) {
      console.error('Import error:', error);
      addToast({
        type: 'error',
        title: 'Import Failed',
        description: error.message || 'Failed to import conversation',
        duration: 5000,
      });
    } finally {
      setIsProcessing(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const parseImportedFile = (content: string, filename: string): Message[] => {
    const extension = filename.split('.').pop()?.toLowerCase();

    try {
      switch (extension) {
        case 'json':
          return parseJSON(content);
        case 'md':
        case 'markdown':
          return parseMarkdown(content);
        case 'txt':
          return parseText(content);
        default:
          throw new Error(`Unsupported file format: ${extension}`);
      }
    } catch (error: any) {
      throw new Error(`Failed to parse ${extension?.toUpperCase()} file: ${error.message}`);
    }
  };

  const parseJSON = (content: string): Message[] => {
    const data = JSON.parse(content);

    // Handle Junas export format
    if (data.messages && Array.isArray(data.messages)) {
      return data.messages.map((msg: any, index: number) => ({
        id: msg.id || `imported-${Date.now()}-${index}`,
        role: msg.role || 'user',
        content: msg.content || '',
        timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
      }));
    }

    // Handle array of messages
    if (Array.isArray(data)) {
      return data.map((msg: any, index: number) => ({
        id: msg.id || `imported-${Date.now()}-${index}`,
        role: msg.role || 'user',
        content: msg.content || '',
        timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
      }));
    }

    throw new Error('Invalid JSON format');
  };

  const parseMarkdown = (content: string): Message[] => {
    const messages: Message[] = [];
    const lines = content.split('\n');
    let currentRole: 'user' | 'assistant' | 'system' = 'user';
    let currentContent: string[] = [];
    let messageIndex = 0;

    const saveCurrentMessage = () => {
      if (currentContent.length > 0) {
        messages.push({
          id: `imported-${Date.now()}-${messageIndex++}`,
          role: currentRole,
          content: currentContent.join('\n').trim(),
          timestamp: new Date(),
        });
        currentContent = [];
      }
    };

    for (const line of lines) {
      // Check for role headers
      if (line.match(/^##\s*(User|Assistant|System)/i)) {
        saveCurrentMessage();
        const role = line.match(/^##\s*(User|Assistant|System)/i)?.[1].toLowerCase();
        currentRole = (role as 'user' | 'assistant' | 'system') || 'user';
      } else if (line.trim() && !line.startsWith('#') && !line.startsWith('**Generated:**') && !line.startsWith('**Total Messages:**') && !line.startsWith('---')) {
        currentContent.push(line);
      }
    }

    saveCurrentMessage();
    return messages;
  };

  const parseText = (content: string): Message[] => {
    const messages: Message[] = [];
    const lines = content.split('\n');
    let currentRole: 'user' | 'assistant' | 'system' = 'user';
    let currentContent: string[] = [];
    let messageIndex = 0;

    const saveCurrentMessage = () => {
      if (currentContent.length > 0) {
        messages.push({
          id: `imported-${Date.now()}-${messageIndex++}`,
          role: currentRole,
          content: currentContent.join('\n').trim(),
          timestamp: new Date(),
        });
        currentContent = [];
      }
    };

    for (const line of lines) {
      // Check for role markers
      if (line.match(/^\[\d+\]\s*(USER|ASSISTANT|SYSTEM)/i)) {
        saveCurrentMessage();
        const role = line.match(/^\[\d+\]\s*(USER|ASSISTANT|SYSTEM)/i)?.[1].toLowerCase();
        currentRole = (role as 'user' | 'assistant' | 'system') || 'user';
      } else if (line.trim() && !line.startsWith('=') && !line.startsWith('-') && !line.startsWith('JUNAS CONVERSATION') && !line.startsWith('Generated:') && !line.startsWith('Total Messages:')) {
        currentContent.push(line);
      }
    }

    saveCurrentMessage();
    return messages;
  };

  const formatOptions = [
    {
      value: 'json' as ImportFormat,
      label: 'JSON',
      description: 'Junas export in JSON format',
      icon: FileJson,
      accept: '.json',
    },
    {
      value: 'markdown' as ImportFormat,
      label: 'Markdown',
      description: 'Junas export in Markdown format',
      icon: FileText,
      accept: '.md,.markdown',
    },
    {
      value: 'txt' as ImportFormat,
      label: 'Plain Text',
      description: 'Junas export in text format',
      icon: FileType,
      accept: '.txt',
    },
  ];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center space-x-2">
            <Upload className="h-5 w-5" />
            <span>Import Conversation</span>
          </DialogTitle>
          <DialogDescription>
            Import a previous Junas conversation export to continue where you left off
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-4">
          {formatOptions.map(option => {
            const Icon = option.icon;
            return (
              <div key={option.value} className="w-full">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isProcessing}
                  className="w-full flex items-start space-x-3 p-4 rounded-lg border-2 border-border hover:border-primary/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
                  <div className="text-left flex-1">
                    <div className="font-medium">{option.label}</div>
                    <div className="text-sm text-muted-foreground">
                      {option.description}
                    </div>
                  </div>
                </button>
              </div>
            );
          })}
        </div>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".json,.md,.markdown,.txt"
          onChange={handleFileSelect}
          className="hidden"
        />

        {isProcessing && (
          <div className="text-sm text-muted-foreground text-center py-2">
            Processing import...
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isProcessing}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
