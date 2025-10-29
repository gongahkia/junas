'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, FileText, Sparkles } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  extractDraftQuery,
  searchTemplatesByKeywords,
  extractAnalysisQuery,
  type LegalTemplate,
  type LegalAnalysisTool
} from '@/lib/templates';
import { AnalysisToolPreview } from './AnalysisToolPreview';

interface MessageInputProps {
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  placeholder?: string;
  onOpenTemplates?: () => void;
  onSelectTemplate?: (template: LegalTemplate) => void;
}

export function MessageInput({
  onSendMessage,
  isLoading,
  placeholder = "Ask Junas anything about Singapore law...",
  onOpenTemplates
}: MessageInputProps) {
  const [message, setMessage] = useState('');
  const [matchedTemplates, setMatchedTemplates] = useState<LegalTemplate[]>([]);
  const [showTemplatePreview, setShowTemplatePreview] = useState(false);
  const [draftQuery, setDraftQuery] = useState<string | null>(null);
  const [analysisMatch, setAnalysisMatch] = useState<{
    tool: LegalAnalysisTool;
    query: string;
  } | null>(null);
  const [showAnalysisPreview, setShowAnalysisPreview] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Detect keywords and search for matching templates or analysis tools
  useEffect(() => {
    // First check for analysis tool keywords
    const analysis = extractAnalysisQuery(message);
    setAnalysisMatch(analysis);

    if (analysis) {
      // Analysis tool detected - show analysis preview
      setShowAnalysisPreview(true);
      setShowTemplatePreview(false);
      setDraftQuery(null);
      setMatchedTemplates([]);
    } else {
      // No analysis tool - check for draft keyword
      const query = extractDraftQuery(message);
      setDraftQuery(query);
      setShowAnalysisPreview(false);

      if (query !== null) {
        const templates = searchTemplatesByKeywords(query);
        setMatchedTemplates(templates);
        setShowTemplatePreview(templates.length > 0);
      } else {
        setMatchedTemplates([]);
        setShowTemplatePreview(false);
      }
    }
  }, [message]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isLoading) return;

    // If analysis tool is detected, use its prompt with the query
    if (analysisMatch) {
      const combinedPrompt = analysisMatch.query
        ? `${analysisMatch.tool.prompt}\n\nUser context: ${analysisMatch.query}`
        : analysisMatch.tool.prompt;
      onSendMessage(combinedPrompt);
      setMessage('');
      setShowAnalysisPreview(false);
      return;
    }

    // If "draft" keyword is detected and we have matching templates, auto-select the best match
    if (draftQuery !== null && matchedTemplates.length > 0) {
      const bestMatch = matchedTemplates[0];
      onSendMessage(bestMatch.prompt);
      setMessage('');
      setShowTemplatePreview(false);
      return;
    }

    // Otherwise, send the message as normal
    onSendMessage(message.trim());
    setMessage('');
  }, [message, isLoading, onSendMessage, draftQuery, matchedTemplates, analysisMatch]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      if (showAnalysisPreview) {
        setShowAnalysisPreview(false);
      } else if (showTemplatePreview) {
        setShowTemplatePreview(false);
      }
    }
  }, [handleSubmit, showTemplatePreview, showAnalysisPreview]);

  const handleTemplateSelect = useCallback((template: LegalTemplate) => {
    onSendMessage(template.prompt);
    setMessage('');
    setShowTemplatePreview(false);
  }, [onSendMessage]);

  const handleAnalysisToolSelect = useCallback((tool: LegalAnalysisTool) => {
    const combinedPrompt = analysisMatch?.query
      ? `${tool.prompt}\n\nUser context: ${analysisMatch.query}`
      : tool.prompt;
    onSendMessage(combinedPrompt);
    setMessage('');
    setShowAnalysisPreview(false);
  }, [onSendMessage, analysisMatch]);

  const isDraftDetected = draftQuery !== null;
  const isAnalysisDetected = analysisMatch !== null;

  return (
    <div className="border-t bg-background relative">
      <div className="max-w-6xl mx-auto px-6 py-6">
        {/* Input form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex items-end space-x-2">
            <div className="flex-1 relative">
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

              {/* Inline suggestion chip */}
              {isAnalysisDetected && !showAnalysisPreview && analysisMatch && (
                <div className="absolute bottom-2 right-2 flex items-center gap-1">
                  <div className="bg-primary/10 text-primary px-2 py-1 rounded-md text-xs flex items-center gap-1 animate-in fade-in slide-in-from-bottom-2">
                    <span className="text-lg">{analysisMatch.tool.icon}</span>
                    <span className="font-medium">
                      {analysisMatch.tool.name} ready
                    </span>
                  </div>
                </div>
              )}
              {!isAnalysisDetected && isDraftDetected && !showTemplatePreview && (
                <div className="absolute bottom-2 right-2 flex items-center gap-1">
                  <div className="bg-primary/10 text-primary px-2 py-1 rounded-md text-xs flex items-center gap-1 animate-in fade-in slide-in-from-bottom-2">
                    <Sparkles className="w-3 h-3" />
                    <span className="font-medium">
                      {matchedTemplates.length > 0
                        ? `${matchedTemplates.length} template${matchedTemplates.length > 1 ? 's' : ''} available`
                        : 'Searching templates...'}
                    </span>
                  </div>
                </div>
              )}
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
            <div className="border rounded-lg bg-card p-4 space-y-3 animate-in fade-in slide-in-from-top-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-primary" />
                  <span className="text-sm font-semibold">
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

              <div className="grid grid-cols-1 gap-2 max-h-[300px] overflow-y-auto">
                {matchedTemplates.slice(0, 5).map((template) => (
                  <Card
                    key={template.id}
                    className="cursor-pointer hover:border-primary hover:bg-accent transition-all"
                    onClick={() => handleTemplateSelect(template)}
                  >
                    <CardHeader className="p-3">
                      <div className="flex items-start gap-2">
                        <FileText className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <CardTitle className="text-sm font-semibold">
                            {template.name}
                          </CardTitle>
                          <CardDescription className="text-xs mt-1">
                            {template.description}
                          </CardDescription>
                          <div className="text-xs text-muted-foreground mt-1">
                            {template.category}
                          </div>
                        </div>
                      </div>
                    </CardHeader>
                  </Card>
                ))}
              </div>

              <div className="text-xs text-muted-foreground text-center pt-2 border-t">
                Click a template to use it, or press Enter to use the best match
                {matchedTemplates.length > 5 && ` • Showing top 5 of ${matchedTemplates.length} matches`}
              </div>
            </div>
          )}

          {/* Help text */}
          <div className="flex items-center justify-end">
            <div className="text-xs text-muted-foreground">
              Press Enter to send, Shift+Enter for new line.
              {isAnalysisDetected && ' Use analysis tools like "irac", "ratio", "obiter".'}
              {!isAnalysisDetected && isDraftDetected && ' Type "draft [document]" to see templates.'}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
