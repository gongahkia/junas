'use client';

import { ThinkingStage } from '@/types/chat';
import { Brain, Sparkles, CheckCircle2, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import remarkMath from 'remark-math';

interface ThinkingStagesProps {
  stages: ThinkingStage[];
}

const stageIcons = {
  initial: Brain,
  critique: Sparkles,
  react: CheckCircle2,
};

const stageColors = {
  initial: 'text-blue-500',
  critique: 'text-purple-500',
  react: 'text-amber-500',
};

export function ThinkingStages({ stages }: ThinkingStagesProps) {
  if (!stages || stages.length === 0) return null;

  return (
    <div className="flex justify-center w-full px-6 py-4">
      <div className="max-w-4xl w-full space-y-6">
        {stages.map((stage, index) => {
          const Icon = stageIcons[stage.stage];
          const colorClass = stageColors[stage.stage];
          const isLoading = stage.isStreaming && !stage.isComplete;
          const hasContent = stage.content && stage.content.trim().length > 0;

          return (
            <div key={`${stage.stage}-${index}`} className="space-y-4">
              <div
                className="rounded-lg border border-border/50 bg-muted/30 backdrop-blur-sm p-4 opacity-60 transition-opacity hover:opacity-80"
              >
                <div className="flex items-center gap-2 mb-3">
                  {isLoading && !hasContent ? (
                    <Loader2 className={`h-4 w-4 ${colorClass} animate-spin`} />
                  ) : (
                    <Icon className={`h-4 w-4 ${colorClass}`} />
                  )}
                  <span className="text-sm font-medium text-muted-foreground">
                    {stage.label}
                  </span>
                  {isLoading && hasContent && (
                    <span className="text-xs text-muted-foreground/60 ml-auto animate-pulse">
                      thinking...
                    </span>
                  )}
                </div>

                {!hasContent && isLoading ? (
                  <div className="flex items-center gap-2 text-muted-foreground/60 text-sm animate-pulse">
                    <span>• • •</span>
                  </div>
                ) : (
                  <div className="prose prose-sm max-w-none text-muted-foreground/90">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                      components={{
                        code: ({ node, className, children, ...props }: any) => {
                          const match = /language-(\w+)/.exec(className || '');
                          const inline = !match;
                          return !inline && match ? (
                            <pre className="bg-muted/50 p-3 rounded-md overflow-x-auto">
                              <code className={className} {...props}>
                                {children}
                              </code>
                            </pre>
                          ) : (
                            <code className="bg-muted/50 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
                              {children}
                            </code>
                          );
                        },
                        p: ({ children }) => (
                          <p className="text-sm leading-relaxed">{children}</p>
                        ),
                      }}
                    >
                      {stage.content}
                    </ReactMarkdown>
                  </div>
                )}
              </div>

              {/* Show vertical line between stages when waiting for next stage */}
              {!stage.isComplete && index < stages.length - 1 && (
                <div className="flex justify-center py-2">
                  <div className="flex flex-col items-center gap-2 opacity-40">
                    <div className="w-0.5 h-8 bg-border animate-pulse" />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
