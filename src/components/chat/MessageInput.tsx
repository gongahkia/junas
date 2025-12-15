'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { InlineProviderSelector } from './InlineProviderSelector';
import { CommandPalette } from './CommandPalette';
import { ContextAttachment, AttachedFile } from './ContextAttachment';

interface MessageInputProps {
  onSendMessage: (content: string, attachedFiles?: AttachedFile[]) => void;
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
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
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

  const handleFilesAttach = useCallback((files: AttachedFile[]) => {
    setAttachedFiles(prev => [...prev, ...files]);
  }, []);

  const handleFileRemove = useCallback((fileId: string) => {
    setAttachedFiles(prev => prev.filter(f => f.id !== fileId));
  }, []);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isLoading) return;

    onSendMessage(message.trim(), attachedFiles.length > 0 ? attachedFiles : undefined);
    setMessage('');
    setAttachedFiles([]);
  }, [message, isLoading, attachedFiles, onSendMessage]);

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
          <div className="flex-1 relative border border-muted-foreground/30 bg-muted/10">
            {/* ASCII top border */}
            <div className="text-xs text-muted-foreground/50 px-2 pt-1 font-mono">
              ┌{'─'.repeat(70)}
            </div>

            {/* Command Palette */}
            {showCommandPalette && (
              <CommandPalette
                onCommandSelect={handleCommandSelect}
                onClose={() => setShowCommandPalette(false)}
                inputValue={message}
                cursorPosition={cursorPosition}
              />
            )}

            <Textarea
              ref={textareaRef}
              value={message}
              onChange={handleMessageChange}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={isLoading}
              className="min-h-[60px] md:min-h-[80px] max-h-[200px] md:max-h-[300px] resize-none text-sm md:text-base pb-12 px-3 md:px-4 pt-2 md:pt-3 font-mono border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
              rows={1}
              data-tour="message-input"
            />

            {/* Bottom toolbar inside textarea */}
            <div className="absolute bottom-3 left-3 right-3 md:bottom-3 md:left-4 md:right-4 flex items-center justify-between z-10">
              <div className="flex items-center gap-1">
                {/* Provider selector */}
                <InlineProviderSelector
                  currentProvider={currentProvider}
                  onProviderChange={onProviderChange}
                />

                {/* Context attachment button */}
                <ContextAttachment
                  onFilesAttach={handleFilesAttach}
                  attachedFiles={attachedFiles}
                  onFileRemove={handleFileRemove}
                  disabled={isLoading}
                />
              </div>

              {/* Helper text */}
              <div className="text-xs text-muted-foreground hidden md:block">
                <kbd className="px-1.5 py-0.5 text-xs font-semibold bg-muted rounded border">
                  /
                </kbd>
                {' '}for commands
              </div>
            </div>
          </div>

          {/* Attached files display */}
          {attachedFiles.length > 0 && (
            <ContextAttachment
              onFilesAttach={handleFilesAttach}
              attachedFiles={attachedFiles}
              onFileRemove={handleFileRemove}
              disabled={isLoading}
            />
          )}
        </form>
      </div>
    </div>
  );
}
