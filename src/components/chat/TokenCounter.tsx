'use client';

import { useEffect, useState } from 'react';

interface TokenCounterProps {
  content: string;
  isStreaming?: boolean;
  provider?: string;
  model?: string;
}

// Token estimation (rough approximation: 1 token ≈ 4 characters)
function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

// Cost per 1K tokens (as of 2024)
const PRICING = {
  gemini: {
    'gemini-2.0-flash-exp': { input: 0, output: 0 }, // Free during preview
    'gemini-1.5-pro': { input: 0.00125, output: 0.005 },
  },
  openai: {
    'gpt-4o': { input: 0.0025, output: 0.01 },
    'gpt-4-turbo': { input: 0.01, output: 0.03 },
  },
  claude: {
    'claude-3-5-sonnet-20241022': { input: 0.003, output: 0.015 },
    'claude-3-opus-20240229': { input: 0.015, output: 0.075 },
  },
};

function estimateCost(tokens: number, provider: string, model: string): number {
  const pricing = PRICING[provider as keyof typeof PRICING]?.[model] || { input: 0, output: 0 };
  // Assuming output tokens for simplicity
  return (tokens / 1000) * pricing.output;
}

export function TokenCounter({ content, isStreaming, provider = 'gemini', model = 'gemini-2.0-flash-exp' }: TokenCounterProps) {
  const [tokens, setTokens] = useState(0);
  const [cost, setCost] = useState(0);

  useEffect(() => {
    const estimatedTokens = estimateTokens(content);
    setTokens(estimatedTokens);
    setCost(estimateCost(estimatedTokens, provider, model));
  }, [content, provider, model]);

  if (!content) return null;

  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground">
      <div className="flex items-center gap-1.5">
        <span className="font-mono">{tokens.toLocaleString()}</span>
        <span>tokens</span>
        {isStreaming && (
          <span className="animate-pulse">...</span>
        )}
      </div>
      {cost > 0 && (
        <div className="flex items-center gap-1.5">
          <span className="opacity-60">·</span>
          <span className="font-mono">${cost.toFixed(4)}</span>
          <span>est.</span>
        </div>
      )}
    </div>
  );
}
