'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Textarea } from '@/components/ui/textarea';
// import { InlineProviderSelector } from './InlineProviderSelector';
import { CommandPalette } from './CommandPalette';

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
  placeholder = "Ask Junas anything about Singapore law... (Type / for commands)",
  currentProvider,
  onProviderChange,
}: MessageInputProps) {
  const [message, setMessage] = useState('');
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [cursorPosition, setCursorPosition] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Handle input changes and detect "/" for command palette
  const handleMessageChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    const newCursorPos = e.target.selectionStart || 0;
    
    setMessage(newValue);
    setCursorPosition(newCursorPos);

    // Check if user typed "/" at the start or after a space
    const beforeCursor = newValue.slice(0, newCursorPos);
    const lastChar = beforeCursor[beforeCursor.length - 1];
    const charBeforeLast = beforeCursor[beforeCursor.length - 2];
    
    if (lastChar === '/' && (!charBeforeLast || charBeforeLast === ' ' || charBeforeLast === '\n')) {
      setShowCommandPalette(true);
    } else if (showCommandPalette) {
      // Check if we should close the palette
      const lastSlashIndex = beforeCursor.lastIndexOf('/');
      if (lastSlashIndex === -1 || beforeCursor.slice(lastSlashIndex).includes(' ')) {
        setShowCommandPalette(false);
      }
    }
  }, [showCommandPalette]);

  const handleCommandSelect = useCallback((commandId: string, commandText: string) => {
    if (!textareaRef.current) return;

    const beforeCursor = message.slice(0, cursorPosition);
    const afterCursor = message.slice(cursorPosition);
    const lastSlashIndex = beforeCursor.lastIndexOf('/');
    
    if (lastSlashIndex !== -1) {
      const newMessage = beforeCursor.slice(0, lastSlashIndex) + commandText + ' ' + afterCursor;
      setMessage(newMessage);
      
      // Set cursor position after the command
      setTimeout(() => {
        if (textareaRef.current) {
          const newCursorPos = lastSlashIndex + commandText.length + 1;
          textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
          textareaRef.current.focus();
        }
      }, 0);
    }
    
    setShowCommandPalette(false);
  }, [message, cursorPosition]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isLoading) return;

    onSendMessage(message.trim());
    setMessage('');
  }, [message, isLoading, onSendMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    // Close command palette on Escape
    if (e.key === 'Escape' && showCommandPalette) {
      e.preventDefault();
      setShowCommandPalette(false);
      return;
    }

    // Don't submit when command palette is open and user presses Enter
    if (e.key === 'Enter' && showCommandPalette) {
      return; // Let CommandPalette handle it
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }, [handleSubmit, showCommandPalette]);

  // Update cursor position on selection change
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const handleSelect = () => {
      setCursorPosition(textarea.selectionStart || 0);
    };

    textarea.addEventListener('select', handleSelect);
    textarea.addEventListener('click', handleSelect);

    return () => {
      textarea.removeEventListener('select', handleSelect);
      textarea.removeEventListener('click', handleSelect);
    };
  }, []);

  return (
    <div className="border-t bg-background sticky bottom-0 z-50 shadow-sm">
      <div className="max-w-5xl mx-auto px-4 md:px-8 py-4 md:py-6">
        {/* Input form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex-1 relative">
            {/* Command Palette */}
            {showCommandPalette && (
              <CommandPalette
                onCommandSelect={handleCommandSelect}
                onClose={() => setShowCommandPalette(false)}
                inputValue={message}
                cursorPosition={cursorPosition}
              />
            )}

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
                  {/* Provider selector replaced with Config button */}
                  <button
                    type="button"
                    className="text-xs hover:bg-accent px-2 py-1 transition-colors font-mono"
                    onClick={() => {
                      if (typeof window !== 'undefined') {
                        const event = new CustomEvent('open-config-dialog', { detail: { tab: 'providers' } });
                        window.dispatchEvent(event);
                      }
                    }}
                  >
                    [ Configure Providers ]
                  </button>
                </div>

                {/* Helper text */}
                <div className="text-xs text-muted-foreground hidden md:block">
                  [ / for commands ]
                </div>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
