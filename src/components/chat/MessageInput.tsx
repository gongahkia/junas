'use client';

import { useState, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send } from 'lucide-react';

interface MessageInputProps {
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  placeholder?: string;
}

export function MessageInput({
  onSendMessage,
  isLoading,
  placeholder = "Ask Junas anything about Singapore law..."
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
        <form onSubmit={handleSubmit} className="space-y-3 md:space-y-4">
          <div className="flex items-end space-x-2">
            <div className="flex-1 relative">
              <Textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={isLoading}
                className="min-h-[60px] md:min-h-[80px] max-h-[200px] md:max-h-[300px] resize-none text-sm md:text-base"
                rows={1}
              />

              {/* Inline suggestion chip */}
              {isAnalysisDetected && !showAnalysisPreview && analysisMatch && (
                <div className="absolute bottom-1 md:bottom-2 right-1 md:right-2 flex items-center gap-1">
                  <div className="bg-primary/10 text-primary px-1.5 md:px-2 py-0.5 md:py-1 rounded-md text-[10px] md:text-xs flex items-center gap-1 animate-in fade-in slide-in-from-bottom-2">
                    <span className="font-medium">
                      {analysisMatch.tool.name} ready
                    </span>
                  </div>
                </div>
              )}
              {!isAnalysisDetected && isDraftDetected && !showTemplatePreview && (
                <div className="absolute bottom-1 md:bottom-2 right-1 md:right-2 flex items-center gap-1">
                  <div className="bg-primary/10 text-primary px-1.5 md:px-2 py-0.5 md:py-1 rounded-md text-[10px] md:text-xs flex items-center gap-1 animate-in fade-in slide-in-from-bottom-2">
                    <Sparkles className="w-3 h-3" />
                    <span className="font-medium hidden sm:inline">
                      {matchedTemplates.length > 0
                        ? `${matchedTemplates.length} template${matchedTemplates.length > 1 ? 's' : ''} available`
                        : 'Searching templates...'}
                    </span>
                    <span className="font-medium sm:hidden">
                      {matchedTemplates.length > 0 ? `${matchedTemplates.length}` : '...'}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Send button */}
            <Button
              type="submit"
              disabled={!message.trim() || isLoading}
              className="h-9 w-9 md:h-10 md:w-10 flex-shrink-0"
            >
              <Send className="h-3.5 w-3.5 md:h-4 md:w-4" />
              <span className="sr-only">Send message</span>
            </Button>
          </div>

          {/* Analysis Tool preview */}
          {showAnalysisPreview && analysisMatch && (
            <AnalysisToolPreview
              tool={analysisMatch.tool}
              query={analysisMatch.query}
              onSelect={handleAnalysisToolSelect}
              onDismiss={() => setShowAnalysisPreview(false)}
            />
          )}

          {/* Template preview dropdown */}
          {showTemplatePreview && matchedTemplates.length > 0 && (
            <div className="border rounded-lg bg-card p-3 md:p-4 space-y-2 md:space-y-3 animate-in fade-in slide-in-from-top-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 md:w-4 md:h-4 text-primary" />
                  <span className="text-xs md:text-sm font-semibold">
                    {matchedTemplates.length === 1
                      ? 'Matching Template'
                      : `${matchedTemplates.length} Matching Templates`}
                  </span>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowTemplatePreview(false)}
                  className="h-6 w-6 p-0"
                >
                  <span className="text-xs">✕</span>
                </Button>
              </div>

              <div className="grid grid-cols-1 gap-2 max-h-[200px] md:max-h-[300px] overflow-y-auto">
                {matchedTemplates.slice(0, 5).map((template) => (
                  <Card
                    key={template.id}
                    className="cursor-pointer hover:border-primary hover:bg-accent transition-all"
                    onClick={() => handleTemplateSelect(template)}
                  >
                    <CardHeader className="p-2 md:p-3">
                      <div className="flex items-start gap-2">
                        <FileText className="w-3.5 h-3.5 md:w-4 md:h-4 text-primary mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <CardTitle className="text-xs md:text-sm font-semibold">
                            {template.name}
                          </CardTitle>
                          <CardDescription className="text-[10px] md:text-xs mt-1">
                            {template.description}
                          </CardDescription>
                          <div className="text-[10px] md:text-xs text-muted-foreground mt-1">
                            {template.category}
                          </div>
                        </div>
                      </div>
                    </CardHeader>
                  </Card>
                ))}
              </div>

              <div className="text-[10px] md:text-xs text-muted-foreground text-center pt-2 border-t">
                <span className="hidden sm:inline">Click a template to use it, or press Enter to use the best match</span>
                <span className="sm:hidden">Tap to use</span>
                {matchedTemplates.length > 5 && ` • Showing top 5 of ${matchedTemplates.length} matches`}
              </div>
            </div>
          )}

          {/* Help text */}
          <div className="flex items-center justify-end">
            <div className="text-[10px] md:text-xs text-muted-foreground">
              <span className="hidden sm:inline">Press Enter to send, Shift+Enter for new line.</span>
              <span className="sm:hidden">Enter to send</span>
              {isAnalysisDetected && <span className="hidden md:inline"> Use analysis tools like "irac", "ratio", "obiter".</span>}
              {!isAnalysisDetected && isDraftDetected && <span className="hidden md:inline"> Type "draft [document]" to see templates.</span>}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
