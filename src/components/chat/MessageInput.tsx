'use client';

import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { InlineProviderSelector } from './InlineProviderSelector';
import { CommandSuggestions } from './CommandSuggestions';
import { COMMANDS } from '@/lib/commands/command-processor';
import Fuse from 'fuse.js';
import { Book } from 'lucide-react';
import { StorageManager } from '@/lib/storage';
import { Snippet } from '@/types/chat';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

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

  // History state
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [draft, setDraft] = useState('');

  // Snippet state
  const [snippets, setSnippets] = useState<Snippet[]>([]);

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
    
    // Load snippets
    const loadSnippets = () => {
        const settings = StorageManager.getSettings();
        setSnippets(settings.snippets || []);
    };
    loadSnippets();
    window.addEventListener('junas-settings-change', loadSnippets);
    return () => window.removeEventListener('junas-settings-change', loadSnippets);
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

  const insertSnippet = (content: string) => {
      // Insert at cursor position or append
      if (textareaRef.current) {
          const start = textareaRef.current.selectionStart;
          const end = textareaRef.current.selectionEnd;
          const text = message;
          const newText = text.substring(0, start) + content + text.substring(end);
          setMessage(newText);
          
          // Move cursor
          setTimeout(() => {
              if (textareaRef.current) {
                  textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + content.length;
                  textareaRef.current.focus();
              }
          }, 0);
      } else {
          setMessage(prev => prev + content);
      }
  };

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isLoading) return;

    const trimmedMessage = message.trim();
    onSendMessage(trimmedMessage);
    
    setHistory(prev => {
        // Don't duplicate if identical to last message
        if (prev.length > 0 && prev[prev.length - 1] === trimmedMessage) return prev;
        return [...prev, trimmedMessage];
    });
    setHistoryIndex(-1);
    setDraft('');
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

    // History navigation
    if (e.key === 'ArrowUp') {
      if (history.length > 0) {
        e.preventDefault();
        const newIndex = historyIndex === -1 ? history.length - 1 : Math.max(0, historyIndex - 1);
        if (historyIndex === -1) setDraft(message);
        setHistoryIndex(newIndex);
        setMessage(history[newIndex]);
        
        // Move cursor to end (needs timeout to wait for render)
        setTimeout(() => {
            if (textareaRef.current) {
                textareaRef.current.selectionStart = textareaRef.current.value.length;
                textareaRef.current.selectionEnd = textareaRef.current.value.length;
            }
        }, 0);
      }
    } else if (e.key === 'ArrowDown') {
      if (historyIndex !== -1) {
        e.preventDefault();
        const newIndex = historyIndex + 1;
        if (newIndex >= history.length) {
          setHistoryIndex(-1);
          setMessage(draft);
        } else {
          setHistoryIndex(newIndex);
          setMessage(history[newIndex]);
        }
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }, [handleSubmit, showSuggestions, suggestionIndex, commandQuery, fuse, history, historyIndex, draft, message]);
  
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

                  {/* Snippets Button */}
                  {snippets.length > 0 && (
                      <Popover>
                        <PopoverTrigger asChild>
                            <button 
                                className="flex items-center gap-1.5 px-2 py-1 hover:bg-muted/50 rounded-sm transition-colors text-muted-foreground hover:text-foreground"
                                title="Insert Snippet"
                                type="button"
                            >
                                <Book className="h-3.5 w-3.5" />
                                <span className="hidden sm:inline">Snippets</span>
                            </button>
                        </PopoverTrigger>
                        <PopoverContent className="w-64 p-2" align="start">
                            <div className="space-y-1">
                                <h4 className="font-medium text-xs px-2 py-1 text-muted-foreground uppercase tracking-wider">Saved Snippets</h4>
                                {snippets.map(snippet => (
                                    <button
                                        key={snippet.id}
                                        onClick={() => insertSnippet(snippet.content)}
                                        className="w-full text-left px-2 py-1.5 text-xs hover:bg-muted rounded-sm truncate transition-colors font-mono"
                                        title={snippet.content}
                                    >
                                        {snippet.title}
                                    </button>
                                ))}
                            </div>
                        </PopoverContent>
                      </Popover>
                  )}
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
