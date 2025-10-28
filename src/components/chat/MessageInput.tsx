'use client';

import { useState, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, FileText } from 'lucide-react';

interface MessageInputProps {
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  placeholder?: string;
  onOpenTemplates?: () => void;
}

export function MessageInput({
  onSendMessage,
  isLoading,
  placeholder = "Ask Junas anything about Singapore law...",
  onOpenTemplates
}: MessageInputProps) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isLoading) return;

    onSendMessage(message.trim());
    setMessage('');
  }, [message, isLoading, onSendMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }, [handleSubmit]);

  return (
    <div className="border-t bg-background">
      <div className="max-w-6xl mx-auto px-6 py-6">
        {/* Input form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex items-end space-x-2">
            <div className="flex-1">
              <Textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={isLoading}
                className="min-h-[80px] max-h-[300px] resize-none"
                rows={1}
              />
            </div>

            {/* Send button */}
            <Button
              type="submit"
              disabled={!message.trim() || isLoading}
              className="h-10 w-10"
            >
              <Send className="h-4 w-4" />
              <span className="sr-only">Send message</span>
            </Button>
          </div>

          {/* Template button and help text */}
          <div className="flex items-center justify-between">
            {onOpenTemplates && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onOpenTemplates}
                className="text-xs"
              >
                <FileText className="w-3 h-3 mr-1" />
                Legal Templates
              </Button>
            )}
            <div className="text-xs text-muted-foreground ml-auto">
              Press Enter to send, Shift+Enter for new line.
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
