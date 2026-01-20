'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Textarea } from '@/components/ui/textarea';
// import { InlineProviderSelector } from './InlineProviderSelector';
import { ModelProviderStatus } from './ModelProviderStatus';

interface MessageInputProps {
  // Removed InlineProviderSelector import as provider selection is now in ConfigDialog
  // import { InlineProviderSelector } from './InlineProviderSelector';
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
  const [isMac, setIsMac] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setIsMac(navigator.platform.toUpperCase().indexOf('MAC') >= 0);
  }, []);

  // Handle input changes
  const handleMessageChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
  }, []);

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
      <div className="max-w-5xl mx-auto px-4 md:px-8 py-4 md:py-6">
        {/* Input form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex-1 relative">

            <div className="border border-muted-foreground/30 bg-muted/10">
              <Textarea
                ref={textareaRef}
                value={message}
                onChange={handleMessageChange}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={isLoading}
                className="min-h-[60px] md:min-h-[80px] max-h-[200px] md:max-h-[300px] resize-none text-sm md:text-base px-3 md:px-4 pt-3 md:pt-4 pb-12 font-mono border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 w-full"
                rows={1}
                data-tour="message-input"
              />

              {/* Bottom toolbar */}
              <div className="border-t border-muted-foreground/30 px-3 md:px-4 py-2 flex items-center justify-between text-xs font-mono bg-muted/5">
                <div className="flex items-center gap-2 md:gap-3">
                  {/* Model/provider status display */}
                  <span className="px-2 py-1"><ModelProviderStatus /></span>
                </div>

                {/* Helper text */}
                <div className="text-xs text-muted-foreground hidden md:block">
                  [ {isMac ? '⌘' : 'Ctrl'} + Shift + P for command palette ]
                </div>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
