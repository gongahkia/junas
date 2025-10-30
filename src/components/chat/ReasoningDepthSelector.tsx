'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { Brain, Zap, Sparkles, CheckCircle } from 'lucide-react';
import { ReasoningDepth } from '@/lib/prompts/system-prompts';

interface ReasoningDepthSelectorProps {
  value: ReasoningDepth | 'auto';
  onChange: (depth: ReasoningDepth | 'auto') => void;
  disabled?: boolean;
}

const depthConfig = {
  auto: {
    label: 'Auto',
    icon: Sparkles,
    description: 'Automatically adjust based on query complexity',
    color: 'text-purple-600',
  },
  quick: {
    label: 'Quick',
    icon: Zap,
    description: 'Fast responses',
    color: 'text-green-600',
  },
  standard: {
    label: 'Standard',
    icon: Brain,
    description: 'Balanced reasoning',
    color: 'text-blue-600',
  },
  deep: {
    label: 'Deep',
    icon: Brain,
    description: 'Thorough analysis',
    color: 'text-indigo-600',
  },
  expert: {
    label: 'Expert',
    icon: Sparkles,
    description: 'Maximum depth',
    color: 'text-amber-600',
  },
};

export function ReasoningDepthSelector({
  value,
  onChange,
  disabled = false,
}: ReasoningDepthSelectorProps) {
  const CurrentIcon = depthConfig[value].icon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          disabled={disabled}
          className="h-9 px-2 text-muted-foreground"
          title="Adjust reasoning depth"
        >
          <CurrentIcon className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="text-xs font-semibold text-muted-foreground">
          Reasoning Depth
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {(Object.keys(depthConfig) as Array<ReasoningDepth | 'auto'>).map((depth) => {
          const config = depthConfig[depth];
          const Icon = config.icon;
          const isSelected = value === depth;

          return (
            <DropdownMenuItem
              key={depth}
              onClick={() => onChange(depth)}
              className="flex items-start gap-2 py-2 cursor-pointer"
            >
              <Icon className={`h-4 w-4 mt-0.5 ${config.color}`} />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{config.label}</span>
                  {isSelected && (
                    <CheckCircle className="h-3 w-3 text-primary" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {config.description}
                </p>
              </div>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
