"use client";

import React from 'react';

export const ThinkingIndicator: React.FC = () => {
  return (
    <div className="flex items-start gap-3 px-4 py-3 max-w-4xl">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
        <span className="text-white text-sm font-semibold">J</span>
      </div>

      <div className="flex-1 pt-1.5">
        <div className="inline-flex items-center gap-2 px-4 py-3 bg-muted/40 rounded-2xl backdrop-blur-sm">
          <div className="flex gap-1">
            <div
              className="w-2 h-2 bg-foreground/60 rounded-full animate-bounce"
              style={{ animationDelay: '0ms', animationDuration: '1s' }}
            />
            <div
              className="w-2 h-2 bg-foreground/60 rounded-full animate-bounce"
              style={{ animationDelay: '150ms', animationDuration: '1s' }}
            />
            <div
              className="w-2 h-2 bg-foreground/60 rounded-full animate-bounce"
              style={{ animationDelay: '300ms', animationDuration: '1s' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
