'use client';

import { Brain, Sparkles, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ReasoningIndicatorProps {
  stage?: 'initial' | 'critique' | 'react' | 'complete';
  currentStage?: number;
  totalStages?: number;
  complexity?: 'simple' | 'moderate' | 'complex' | 'expert';
  reasoningDepth?: 'quick' | 'standard' | 'deep' | 'expert';
  className?: string;
}

const complexityColors = {
  simple: 'text-muted-foreground bg-muted border-border',
  moderate: 'text-muted-foreground bg-muted border-border',
  complex: 'text-foreground bg-muted border-border',
  expert: 'text-foreground bg-muted border-border',
};

const complexityLabels = {
  simple: 'Simple',
  moderate: 'Moderate',
  complex: 'Complex',
  expert: 'Expert',
};

const stageLabels = {
  initial: 'Initial Analysis',
  critique: 'Self-Critique',
  react: 'Expert ReAct',
  complete: 'Complete',
};

export function ReasoningIndicator({
  stage,
  currentStage,
  totalStages,
  complexity,
  reasoningDepth,
  className,
}: ReasoningIndicatorProps) {
  if (!stage && !complexity) return null;

  return (
    <div className={cn('flex items-center gap-2 text-xs', className)}>
      {/* Reasoning in progress */}
      {stage && stage !== 'complete' && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Brain className="h-3.5 w-3.5 animate-pulse" />
          <span>
            {stageLabels[stage]}
            {currentStage && totalStages && ` (${currentStage}/${totalStages})`}
          </span>
        </div>
      )}

      {/* Complexity badge */}
      {complexity && (
        <div
          className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs font-medium',
            complexityColors[complexity]
          )}
        >
          {complexity === 'expert' && <Sparkles className="h-3 w-3" />}
          <span>{complexityLabels[complexity]} Analysis</span>
        </div>
      )}

      {/* Reasoning depth indicator */}
      {reasoningDepth && reasoningDepth !== 'quick' && (
        <div className="flex items-center gap-1 text-muted-foreground">
          <span className="text-xs">
            {reasoningDepth === 'deep' && 'Deep Reasoning'}
            {reasoningDepth === 'expert' && 'Expert Reasoning'}
            {reasoningDepth === 'standard' && 'Standard Reasoning'}
          </span>
        </div>
      )}

      {/* Complete indicator */}
      {stage === 'complete' && totalStages && totalStages > 1 && (
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <CheckCircle className="h-3.5 w-3.5" />
          <span>Multi-stage analysis complete ({totalStages} stages)</span>
        </div>
      )}
    </div>
  );
}

/**
 * Reasoning progress bar for multi-stage analysis
 */
interface ReasoningProgressProps {
  currentStage: number;
  totalStages: number;
  stage: string;
}

export function ReasoningProgress({ currentStage, totalStages, stage }: ReasoningProgressProps) {
  const progress = (currentStage / totalStages) * 100;

  return (
    <div className="space-y-2 py-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-2">
          <Brain className="h-3.5 w-3.5 animate-pulse" />
          Stage {currentStage} of {totalStages}: {stage}
        </span>
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary transition-all duration-500 ease-out rounded-full"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
