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
import { generateId } from '@/lib/utils';

interface ImportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onImport: (messages: Message[]) => void;
}

type ImportFormat = 'json' | 'markdown' | 'txt';

export function ImportDialog({ isOpen, onClose, onImport }: ImportDialogProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState<ImportFormat | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addToast } = useToast();

  const validateFileFormat = (file: File, expectedFormat: ImportFormat): boolean => {
    const extension = file.name.split('.').pop()?.toLowerCase();

    switch (expectedFormat) {
      case 'json':
        return extension === 'json';
      case 'markdown':
        return extension === 'md' || extension === 'markdown';
      case 'txt':
        return extension === 'txt';
      default:
        return false;
    }
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsProcessing(true);

    // Use setTimeout to ensure errors are caught by our handler, not React's error boundary
    setTimeout(async () => {
      try {
        // Validate file format matches the selected button
        if (selectedFormat && !validateFileFormat(file, selectedFormat)) {
          const expectedExtensions = selectedFormat === 'json' ? '.json' :
                                    selectedFormat === 'markdown' ? '.md or .markdown' :
                                    '.txt';
          throw new Error(`Invalid file format. Please select a ${expectedExtensions} file for ${selectedFormat.toUpperCase()} import.`);
        }

        const text = await file.text();
        const messages = parseImportedFile(text, file.name);

        if (messages.length === 0) {
          throw new Error('No messages found in the imported file');
        }

        // Pass the messages to be summarized by ChatInterface
        onImport(messages);
        onClose();
      } catch (error: any) {
        console.error('Import error:', error);
        addToast({
          type: 'error',
          title: 'Import Failed',
          description: error.message || 'Failed to import conversation',
          duration: 5000,
        });
        onClose(); // Close dialog on error
      } finally {
        setIsProcessing(false);
        setSelectedFormat(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    }, 0);
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

    // Validate Junas export signature
    if (!data.__junas_export__ || data.__junas_signature__ !== 'JUNAS_LEGAL_AI_EXPORT') {
      throw new Error('This file was not exported from Junas. Only Junas-exported files can be imported.');
    }

    // Handle Junas export format
    if (data.messages && Array.isArray(data.messages)) {
      return data.messages.map((msg: any, index: number) => ({
        id: msg.id || `imported-${Date.now()}-${index}`,
        role: msg.role || 'user',
        content: msg.content || '',
        timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
      }));
    }

    throw new Error('Invalid Junas export format');
  };

  const parseMarkdown = (content: string): Message[] => {
    // Validate Junas export signature
    const signatureMatch = content.match(/<!--\s*__JUNAS_EXPORT__:true\s+__JUNAS_VERSION__:\S+\s+__JUNAS_SIGNATURE__:JUNAS_LEGAL_AI_EXPORT\s*-->/);
    if (!signatureMatch) {
      throw new Error('This file was not exported from Junas. Only Junas-exported files can be imported.');
    }

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
    // Validate Junas export signature (should be in the first line)
    const firstLine = content.split('\n')[0];
    if (!firstLine.includes('__JUNAS_EXPORT__:true') || !firstLine.includes('__JUNAS_SIGNATURE__:JUNAS_LEGAL_AI_EXPORT')) {
      throw new Error('This file was not exported from Junas. Only Junas-exported files can be imported.');
    }

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
      // Skip the signature line
      if (line.includes('__JUNAS_EXPORT__') && line.includes('__JUNAS_SIGNATURE__')) {
        continue;
      }

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
                  onClick={() => {
                    setSelectedFormat(option.value);
                    // Set the accept attribute dynamically
                    if (fileInputRef.current) {
                      fileInputRef.current.accept = option.accept;
                      fileInputRef.current.click();
                    }
                  }}
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
          onChange={handleFileSelect}
          className="hidden"
        />

        {isProcessing && (
          <div className="text-sm text-muted-foreground text-center py-2">
            Importing and summarizing conversation...
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
