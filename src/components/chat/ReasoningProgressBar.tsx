'use client';

import { Brain, Sparkles, CheckCircle2, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ProgressBarProps {
  currentStage: number;
  totalStages: number;
  stage: string;
  isActive?: boolean;
}

export function ReasoningProgressBar({ currentStage, totalStages, stage, isActive = true }: ProgressBarProps) {
  const progress = (currentStage / totalStages) * 100;

  const stageLabels: Record<string, string> = {
    initial: 'Initial Analysis',
    critique: 'Self-Critique',
    react: 'Expert ReAct',
    complete: 'Complete',
  };

  const getStageIcon = (stageName: string) => {
    switch (stageName) {
      case 'initial': return <Brain className="w-4 h-4" />;
      case 'critique': return <Sparkles className="w-4 h-4" />;
      case 'react': return <Brain className="w-4 h-4" />;
      case 'complete': return <CheckCircle2 className="w-4 h-4" />;
      default: return <Brain className="w-4 h-4" />;
    }
  };

  return (
    <div className="w-full bg-muted/30 border-b">
      <div className="max-w-6xl mx-auto px-3 md:px-6 py-3">
        <div className="space-y-2">
          {/* Stage label with icon */}
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-muted-foreground">
              {isActive ? (
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
              ) : (
                getStageIcon(stage)
              )}
              <span className="font-medium">
                {stageLabels[stage] || stage}
              </span>
            </div>
            <span className="text-muted-foreground">
              Step {currentStage} of {totalStages}
            </span>
          </div>
          
          {/* Progress bar */}
          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full bg-primary transition-all duration-300 ease-out',
                isActive && 'animate-pulse'
              )}
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Stage badges */}
          <div className="flex gap-2 flex-wrap">
            {Array.from({ length: totalStages }).map((_, idx) => {
              const stageNum = idx + 1;
              const isComplete = stageNum < currentStage;
              const isCurrent = stageNum === currentStage;
              
              return (
                <div
                  key={idx}
                  className={cn(
                    'px-2 py-0.5 rounded text-xs font-medium transition-colors',
                    isComplete && 'bg-primary/20 text-primary',
                    isCurrent && 'bg-primary text-primary-foreground',
                    !isComplete && !isCurrent && 'bg-muted text-muted-foreground'
                  )}
                >
                  {stageNum}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
