'use client';

import { Button } from '@/components/ui/button';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { LegalAnalysisTool } from '@/lib/templates';

interface AnalysisToolPreviewProps {
  tool: LegalAnalysisTool;
  query: string;
  onSelect: (tool: LegalAnalysisTool) => void;
  onDismiss: () => void;
}

export function AnalysisToolPreview({
  tool,
  query,
  onSelect,
  onDismiss
}: AnalysisToolPreviewProps) {
  return (
    <div className="border rounded-lg bg-card p-4 space-y-3 animate-in fade-in slide-in-from-top-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{tool.icon}</span>
          <span className="text-sm font-semibold">{tool.name}</span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onDismiss}
          className="h-6 w-6 p-0"
        >
          <span className="text-xs">✕</span>
        </Button>
      </div>

      {/* Description */}
      <p className="text-sm text-muted-foreground">{tool.description}</p>

      {/* Structure preview */}
      {tool.structure && tool.structure.length > 0 && (
        <div className="space-y-2">
          <span className="text-xs font-medium text-muted-foreground">
            Analysis Structure:
          </span>
          <div className="flex flex-wrap gap-2">
            {tool.structure.map((section, i) => (
              <span
                key={i}
                className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-secondary text-secondary-foreground"
              >
                {i + 1}. {section}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Category badge */}
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border border-border capitalize">
          {tool.category}
        </span>
      </div>

      {/* Action button */}
      <div className="flex gap-2 pt-2">
        <Button
          type="button"
          onClick={() => onSelect(tool)}
          className="flex-1"
          size="sm"
        >
          Start {tool.name}
        </Button>
      </div>

      {/* Help text */}
      <div className="text-xs text-muted-foreground text-center pt-2 border-t">
        Click to start this analysis workflow, or press Enter
      </div>
    </div>
  );
}
