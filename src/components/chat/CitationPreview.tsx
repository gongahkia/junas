'use client';

import { Citation } from '@/types/chat';
import { ExternalLink, Scale, FileText, BookOpen } from 'lucide-react';
import { Card } from '@/components/ui/card';

interface CitationPreviewProps {
  citation: Citation;
}

export function CitationPreview({ citation }: CitationPreviewProps) {
  const getIcon = () => {
    switch (citation.type) {
      case 'case': return <Scale className="w-3 h-3" />;
      case 'statute': return <FileText className="w-3 h-3" />;
      case 'regulation': return <FileText className="w-3 h-3" />;
      case 'article': return <BookOpen className="w-3 h-3" />;
      default: return <FileText className="w-3 h-3" />;
    }
  };

  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group relative inline-block"
    >
      <div className="flex items-center gap-1 text-xs text-primary hover:underline">
        {getIcon()}
        <span>{citation.title}</span>
        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
      
      {/* Tooltip */}
      <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-50">
        <Card className="p-3 shadow-lg max-w-sm">
          <div className="space-y-2">
            <div className="font-semibold text-sm">{citation.title}</div>
            <div className="text-xs text-muted-foreground space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">Type:</span>
                <span className="capitalize">{citation.type}</span>
              </div>
              {citation.jurisdiction && (
                <div className="flex items-center gap-2">
                  <span className="font-medium">Jurisdiction:</span>
                  <span>{citation.jurisdiction}</span>
                </div>
              )}
              {citation.year && (
                <div className="flex items-center gap-2">
                  <span className="font-medium">Year:</span>
                  <span>{citation.year}</span>
                </div>
              )}
            </div>
            <div className="text-xs text-primary flex items-center gap-1 pt-1">
              <ExternalLink className="w-3 h-3" />
              <span>Click to open source</span>
            </div>
          </div>
        </Card>
      </div>
    </a>
  );
}
