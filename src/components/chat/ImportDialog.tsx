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
import { Upload, FileJson, FileText, FileType, Loader2 } from 'lucide-react';
import { ChatService } from '@/lib/ai/chat-service';
import { generateId } from '@/lib/utils';

interface ImportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onImport: (messages: Message[]) => void;
}

export function ImportDialog({ isOpen, onClose, onImport }: ImportDialogProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const parseJSON = (content: string): Message[] => {
    try {
      const data = JSON.parse(content);

      // Handle our export format
      if (data.messages && Array.isArray(data.messages)) {
        return data.messages.map((m: any) => ({
          id: m.id || generateId(),
          role: m.role,
          content: m.content,
          timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
          attachments: m.attachments,
        }));
      }

      // Handle simple array format
      if (Array.isArray(data)) {
        return data.map((m: any) => ({
          id: m.id || generateId(),
          role: m.role || 'user',
          content: m.content || m.text || '',
          timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
        }));
      }

      throw new Error('Unrecognized JSON format');
    } catch (error) {
      throw new Error('Failed to parse JSON file. Please ensure it is valid JSON.');
    }
  };

  const parseMarkdown = (content: string): Message[] => {
    const messages: Message[] = [];
    const lines = content.split('\n');
    let currentRole: 'user' | 'assistant' | null = null;
    let currentContent: string[] = [];

    for (const line of lines) {
      // Check for role headers
      const userMatch = line.match(/^##\s*(USER|User)/i);
      const assistantMatch = line.match(/^##\s*(ASSISTANT|Assistant)/i);

      if (userMatch || assistantMatch) {
        // Save previous message if exists
        if (currentRole && currentContent.length > 0) {
          messages.push({
            id: generateId(),
            role: currentRole,
            content: currentContent.join('\n').trim(),
            timestamp: new Date(),
          });
        }

        // Start new message
        currentRole = userMatch ? 'user' : 'assistant';
        currentContent = [];
      } else if (currentRole && line.trim() && !line.startsWith('#')) {
        currentContent.push(line);
      }
    }

    // Add last message
    if (currentRole && currentContent.length > 0) {
      messages.push({
        id: generateId(),
        role: currentRole,
        content: currentContent.join('\n').trim(),
        timestamp: new Date(),
      });
    }

    return messages;
  };

  const parseText = (content: string): Message[] => {
    const messages: Message[] = [];
    const lines = content.split('\n');
    let currentRole: 'user' | 'assistant' | null = null;
    let currentContent: string[] = [];

    for (const line of lines) {
      // Check for role markers
      const userMatch = line.match(/^\[\d+\]\s*(USER|User)/i);
      const assistantMatch = line.match(/^\[\d+\]\s*(ASSISTANT|Assistant)/i);

      if (userMatch || assistantMatch) {
        // Save previous message if exists
        if (currentRole && currentContent.length > 0) {
          messages.push({
            id: generateId(),
            role: currentRole,
            content: currentContent.join('\n').trim(),
            timestamp: new Date(),
          });
        }

        // Start new message
        currentRole = userMatch ? 'user' : 'assistant';
        currentContent = [];
      } else if (currentRole && line.trim() && !line.match(/^[-=]+$/)) {
        // Skip separator lines
        if (!line.startsWith('JUNAS CONVERSATION') &&
            !line.startsWith('Generated:') &&
            !line.startsWith('Total Messages:') &&
            !line.startsWith('Attachments:')) {
          currentContent.push(line);
        }
      }
    }

    // Add last message
    if (currentRole && currentContent.length > 0) {
      messages.push({
        id: generateId(),
        role: currentRole,
        content: currentContent.join('\n').trim(),
        timestamp: new Date(),
      });
    }

    return messages;
  };

  const summarizeConversation = async (messages: Message[]): Promise<Message[]> => {
    try {
      // Create a summary request
      const summaryPrompt = `You are summarizing a previous conversation. Please provide a concise summary of the key points, questions asked, and answers provided in the following conversation. Keep it brief but informative.

Conversation:
${messages.map(m => `${m.role.toUpperCase()}: ${m.content}`).join('\n\n')}

Please provide a summary in 2-3 paragraphs.`;

      const summaryMessage: Message = {
        id: generateId(),
        role: 'user',
        content: summaryPrompt,
        timestamp: new Date(),
      };

      // Get summary from AI
      const summary = await ChatService.sendMessage([summaryMessage]);

      // Return summary as a system context message
      return [
        {
          id: generateId(),
          role: 'assistant',
          content: `Previous conversation summary:\n\n${summary}`,
          timestamp: new Date(),
        },
      ];
    } catch (error) {
      console.error('Failed to summarize conversation:', error);
      // On error, just return a simple summary
      return [
        {
          id: generateId(),
          role: 'assistant',
          content: `Previous conversation imported with ${messages.length} messages. Continuing from previous context.`,
          timestamp: new Date(),
        },
      ];
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    try {
      const content = await selectedFile.text();
      let messages: Message[] = [];

      // Parse based on file type
      const extension = selectedFile.name.split('.').pop()?.toLowerCase();

      switch (extension) {
        case 'json':
          messages = parseJSON(content);
          break;
        case 'md':
        case 'markdown':
          messages = parseMarkdown(content);
          break;
        case 'txt':
          messages = parseText(content);
          break;
        default:
          throw new Error('Unsupported file type. Please use .json, .md, or .txt files.');
      }

      if (messages.length === 0) {
        throw new Error('No messages found in file.');
      }

      // Summarize the conversation
      const summarizedMessages = await summarizeConversation(messages);

      // Import the summarized messages
      onImport(summarizedMessages);
      onClose();
      setSelectedFile(null);
    } catch (error: any) {
      alert(error.message || 'Failed to import conversation');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center space-x-2">
            <Upload className="h-5 w-5" />
            <span>Import Conversation</span>
          </DialogTitle>
          <DialogDescription>
            Import a previous conversation. The AI will summarize it to provide context.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,.md,.markdown,.txt"
            onChange={handleFileSelect}
            className="hidden"
          />

          <div
            onClick={handleBrowseClick}
            className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
          >
            <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <p className="text-sm font-medium mb-2">
              {selectedFile ? selectedFile.name : 'Click to select a file'}
            </p>
            <p className="text-xs text-muted-foreground">
              Supports JSON, Markdown, and TXT files
            </p>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Supported formats:</p>
            <div className="grid grid-cols-3 gap-2">
              <div className="flex items-center space-x-2 text-xs">
                <FileJson className="h-4 w-4" />
                <span>.json</span>
              </div>
              <div className="flex items-center space-x-2 text-xs">
                <FileText className="h-4 w-4" />
                <span>.md</span>
              </div>
              <div className="flex items-center space-x-2 text-xs">
                <FileType className="h-4 w-4" />
                <span>.txt</span>
              </div>
            </div>
          </div>

          {isProcessing && (
            <div className="flex items-center justify-center space-x-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Processing and summarizing conversation...</span>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isProcessing}>
            Cancel
          </Button>
          <Button onClick={handleImport} disabled={!selectedFile || isProcessing}>
            {isProcessing ? 'Importing...' : 'Import'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
