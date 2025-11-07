'use client';

import { useState, useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Citation } from '@/types/chat';
import { Scale, FileText, BookOpen, Download } from 'lucide-react';
import { Card } from '@/components/ui/card';

interface CitationManagerProps {
  isOpen: boolean;
  onClose: () => void;
  citations: Citation[];
  onExport?: (format: 'endnote' | 'zotero' | 'bibtex') => void;
}

export function CitationManager({ isOpen, onClose, citations, onExport }: CitationManagerProps) {
  const [selectedFormat, setSelectedFormat] = useState<'endnote' | 'zotero' | 'bibtex'>('bibtex');

  // Deduplicate by citation ID
  const uniqueCitations = useMemo(() => {
    const seen = new Set<string>();
    return citations.filter(c => {
      if (seen.has(c.id)) return false;
      seen.add(c.id);
      return true;
    });
  }, [citations]);

  const getIcon = (type: Citation['type']) => {
    switch (type) {
      case 'case': return <Scale className="w-4 h-4" />;
      case 'statute': return <FileText className="w-4 h-4" />;
      case 'regulation': return <FileText className="w-4 h-4" />;
      case 'article': return <BookOpen className="w-4 h-4" />;
      default: return <FileText className="w-4 h-4" />;
    }
  };

  const groupedByType = useMemo(() => {
    const groups: Record<Citation['type'], Citation[]> = {
      case: [],
      statute: [],
      regulation: [],
      article: [],
    };
    uniqueCitations.forEach(c => groups[c.type].push(c));
    return groups;
  }, [uniqueCitations]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Citations ({uniqueCitations.length})</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Export controls */}
          <div className="flex items-center gap-2 border-b pb-3">
            <span className="text-sm font-medium">Export as:</span>
            <div className="flex gap-2">
              {(['bibtex', 'endnote', 'zotero'] as const).map(fmt => (
                <Button
                  key={fmt}
                  variant={selectedFormat === fmt ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedFormat(fmt)}
                >
                  {fmt.toUpperCase()}
                </Button>
              ))}
            </div>
            <Button size="sm" className="ml-auto" onClick={() => onExport?.(selectedFormat)}>
              <Download className="w-4 h-4 mr-1" />
              Export
            </Button>
          </div>

          {/* Grouped citations */}
          {(Object.entries(groupedByType) as [Citation['type'], Citation[]][]).map(([type, items]) => {
            if (items.length === 0) return null;
            return (
              <div key={type} className="space-y-2">
                <h3 className="text-sm font-semibold capitalize flex items-center gap-2">
                  {getIcon(type)}
                  {type}s ({items.length})
                </h3>
                <div className="space-y-2">
                  {items.map(citation => (
                    <Card key={citation.id} className="p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 space-y-1">
                          <a
                            href={citation.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-primary hover:underline"
                          >
                            {citation.title}
                          </a>
                          <div className="text-xs text-muted-foreground flex gap-3">
                            {citation.jurisdiction && <span>{citation.jurisdiction}</span>}
                            {citation.year && <span>{citation.year}</span>}
                          </div>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}

          {uniqueCitations.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              No citations in this conversation.
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
