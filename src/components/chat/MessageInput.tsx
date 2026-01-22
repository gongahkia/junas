'use client';

import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { InlineProviderSelector } from './InlineProviderSelector';
import { CommandSuggestions } from './CommandSuggestions';
import { COMMANDS } from '@/lib/commands/command-processor';
import Fuse from 'fuse.js';

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
  const [isMac, setIsMac] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // Suggestion state
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [commandQuery, setCommandQuery] = useState('');
  const [suggestionIndex, setSuggestionIndex] = useState(0);

  // Fuse instance for matching logic in handleKeyDown
  const fuse = useMemo(() => {
    return new Fuse(COMMANDS, {
      keys: ['id', 'description', 'label'],
      threshold: 0.4,
      distance: 100,
    });
  }, []);

  useEffect(() => {
    setIsMac(navigator.platform.toUpperCase().indexOf('MAC') >= 0);
  }, []);

  // Handle input changes
  const handleMessageChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    setMessage(newValue);

    // Check for command trigger
    if (newValue.startsWith('/')) {
      // Check if there's a space, which means command is finished
      if (newValue.includes(' ')) {
        setShowSuggestions(false);
        return;
      }

      const match = newValue.match(/^\/([a-zA-Z0-9-]*)$/);
      if (match) {
        setShowSuggestions(true);
        setCommandQuery(match[1]);
        setSuggestionIndex(0);
      } else {
        setShowSuggestions(false);
      }
    } else {
      setShowSuggestions(false);
    }
  }, []);

  const handleCommandSelect = (commandId: string) => {
    setMessage(`/${commandId} `);
    setShowSuggestions(false);
    textareaRef.current?.focus();
  };

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isLoading) return;

    onSendMessage(message.trim());
    setMessage('');
    setShowSuggestions(false);
  }, [message, isLoading, onSendMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (showSuggestions) {
      // Calculate matches to know the count for clamping
      const matches = commandQuery 
        ? fuse.search(commandQuery).map(r => r.item)
        : COMMANDS;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSuggestionIndex(prev => (prev + 1) % matches.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSuggestionIndex(prev => (prev - 1 + matches.length) % matches.length);
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        if (matches[suggestionIndex]) {
          handleCommandSelect(matches[suggestionIndex].id);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setShowSuggestions(false);
      }
      return;
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }, [handleSubmit, showSuggestions, suggestionIndex, commandQuery, fuse]);
  
  return (
    <div className="border-t bg-background sticky bottom-0 z-50 shadow-sm">
      <div className="max-w-5xl mx-auto px-4 md:px-8 py-4 md:py-6">
        {/* Input form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex-1 relative">
            
            {showSuggestions && (
               <CommandSuggestions 
                  query={commandQuery} 
                  onSelect={handleCommandSelect}
                  isOpen={showSuggestions}
                  selectedIndex={suggestionIndex}
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
                  {/* Model/provider status display */}
                  <InlineProviderSelector 
                    currentProvider={currentProvider}
                    onProviderChange={onProviderChange}
                    disabled={isLoading}
                  />
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
