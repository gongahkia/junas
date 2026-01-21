'use client';

import { useState, useEffect } from 'react';
import { getModelsWithStatus, AVAILABLE_MODELS } from '@/lib/ml/model-manager';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ChevronDown, Cpu, Cloud, Globe } from 'lucide-react';

interface InlineProviderSelectorProps {
  currentProvider: string;
  onProviderChange: (provider: string) => void;
  disabled?: boolean;
}

export function InlineProviderSelector({ 
  currentProvider, 
  onProviderChange,
  disabled 
}: InlineProviderSelectorProps) {
  const [configuredProviders, setConfiguredProviders] = useState<string[]>([]);
  const [hasLocalModels, setHasLocalModels] = useState(false);

  useEffect(() => {
    const checkStatus = async () => {
      // Check local models
      const models = getModelsWithStatus();
      const downloadedCount = models.filter(m => m.isDownloaded).length;
      setHasLocalModels(downloadedCount === AVAILABLE_MODELS.length);

      // Check API providers
      try {
        const res = await fetch('/api/auth/keys');
        if (res.ok) {
          const { configured } = await res.json();
          const providers = Object.keys(configured).filter(k => configured[k]);
          setConfiguredProviders(providers);
        }
      } catch (e) {
        console.error('Failed to fetch provider status', e);
      }
    };

    checkStatus();
    // Re-check every 5 seconds or on focus could be better, but once on mount is okay for now
    window.addEventListener('focus', checkStatus);
    return () => window.removeEventListener('focus', checkStatus);
  }, []);

  const getProviderLabel = (id: string) => {
    switch (id) {
      case 'local': return 'Local Models (Offline)';
      case 'gemini': return 'Google Gemini';
      case 'openai': return 'OpenAI GPT-4';
      case 'claude': return 'Anthropic Claude';
      case 'ollama': return 'Ollama (Local)';
      default: return id.charAt(0).toUpperCase() + id.slice(1);
    }
  };

  const getProviderIcon = (id: string) => {
    if (id === 'local' || id === 'ollama') return <Cpu className="h-3 w-3" />;
    return <Cloud className="h-3 w-3" />;
  };

  const availableOptions = [
    ...(hasLocalModels ? ['local'] : []),
    ...configuredProviders
  ];

  if (availableOptions.length === 0) {
    return <span className="text-xs text-muted-foreground">No providers available</span>;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger disabled={disabled} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 outline-none">
        {getProviderIcon(currentProvider)}
        <span className="font-mono">{getProviderLabel(currentProvider)}</span>
        <ChevronDown className="h-3 w-3 opacity-50" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        {availableOptions.map(id => (
          <DropdownMenuItem 
            key={id}
            onClick={() => onProviderChange(id)}
            className="flex items-center gap-2 text-xs font-mono cursor-pointer"
          >
            {getProviderIcon(id)}
            {getProviderLabel(id)}
            {currentProvider === id && <span className="ml-auto">✓</span>}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
