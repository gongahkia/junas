'use client';

import { useState, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send } from 'lucide-react';
import { InlineProviderSelector } from './InlineProviderSelector';

interface MessageInputProps {
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  placeholder?: string;
  currentProvider: string;
  onProviderChange: (provider: string) => void;
}

export function MessageInput({
  onSendMessage,
  isLoading,
  placeholder = "Ask Junas anything about Singapore law...",
  currentProvider,
  onProviderChange,
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
    <div className="border-t bg-background sticky bottom-0 z-50 shadow-sm">
      <div className="max-w-6xl mx-auto px-3 md:px-6 py-3 md:py-6">
        {/* Input form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex items-end space-x-2">
            <div className="flex-1 relative">
              <Textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={isLoading}
                className="min-h-[60px] md:min-h-[80px] max-h-[200px] md:max-h-[300px] resize-none text-sm md:text-base pb-10"
                rows={1}
                data-tour="message-input"
              />
              
              {/* Provider selector - positioned at bottom left inside textarea */}
              <div className="absolute bottom-2 left-2 z-10">
                <InlineProviderSelector
                  currentProvider={currentProvider}
                  onProviderChange={onProviderChange}
                />
              </div>
            </div>

            {/* Send button */}
            <Button
              type="submit"
              disabled={!message.trim() || isLoading}
              className="h-9 w-9 md:h-10 md:w-10 flex-shrink-0"
              data-tour="send-button"
            >
              <Send className="h-3.5 w-3.5 md:h-4 md:w-4" />
              <span className="sr-only">Send message</span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
