"use client";

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { ChevronDown, Eye, EyeOff, ExternalLink, Check, X } from 'lucide-react';

interface Provider {
  id: string;
  name: string;
  apiKeyPlaceholder: string;
  getKeyUrl: string;
}

const providers: Provider[] = [
  {
    id: 'gemini',
    name: 'Gemini',
    apiKeyPlaceholder: 'Enter your Gemini API key',
    getKeyUrl: 'https://aistudio.google.com/app/apikey',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    apiKeyPlaceholder: 'Enter your OpenAI API key',
    getKeyUrl: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'claude',
    name: 'Claude',
    apiKeyPlaceholder: 'Enter your Anthropic API key',
    getKeyUrl: 'https://console.anthropic.com/settings/keys',
  },
];

interface InlineProviderSelectorProps {
  currentProvider: string;
  onProviderChange: (provider: string) => void;
}

export function InlineProviderSelector({
  currentProvider,
  onProviderChange,
}: InlineProviderSelectorProps) {
  const [selectedProvider, setSelectedProvider] = useState(currentProvider);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [configuredProviders, setConfiguredProviders] = useState<Record<string, boolean>>({});
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Sync selectedProvider with currentProvider prop
  useEffect(() => {
    setSelectedProvider(currentProvider);
  }, [currentProvider]);

  // Load configured providers status on mount and when popover opens
  useEffect(() => {
    if (isOpen) {
      checkConfiguredProviders();
    }
  }, [isOpen]);

  useEffect(() => {
    checkConfiguredProviders();
  }, []);

  const checkConfiguredProviders = async () => {
    try {
      const response = await fetch('/api/auth/keys');
      if (response.ok) {
        const { configured, keys } = await response.json();
        setConfiguredProviders(configured);

        // Load existing keys into the form
        setApiKeys(keys || {});

        // If current provider isn't configured, find first configured one
        if (!configured[selectedProvider]) {
          const firstConfigured = providers.find(p => configured[p.id]);
          if (firstConfigured) {
            setSelectedProvider(firstConfigured.id);
            onProviderChange(firstConfigured.id);
          }
        }
      }
    } catch (error) {
      console.error('Error checking providers:', error);
    }
  };

  const handleProviderSelect = (providerId: string) => {
    // Only allow selecting configured providers
    if (configuredProviders[providerId]) {
      setSelectedProvider(providerId);
      onProviderChange(providerId);
      setIsOpen(false);
    }
  };

  const handleApiKeyChange = (providerId: string, value: string) => {
    setApiKeys(prev => ({ ...prev, [providerId]: value }));
  };

  const toggleKeyVisibility = (providerId: string) => {
    setShowKeys(prev => ({ ...prev, [providerId]: !prev[providerId] }));
  };

  const handleSaveKeys = async () => {
    setIsSaving(true);
    try {
      // Transform apiKeys object to match API route expectations
      const payload = {
        gemini: apiKeys.gemini,
        openai: apiKeys.openai,
        claude: apiKeys.claude,
      };

      const response = await fetch('/api/auth/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        // Refresh configured status
        await checkConfiguredProviders();
        setIsOpen(false);
      }
    } catch (error) {
      console.error('Error saving API keys:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const currentProviderData = providers.find(p => p.id === selectedProvider);
  const hasConfiguredProvider = Object.values(configuredProviders).some(v => v);
  const isCurrentProviderConfigured = configuredProviders[selectedProvider];

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button 
          variant="ghost" 
          size="sm" 
          className="h-7 gap-1.5 text-xs px-2 hover:bg-accent"
        >
          <span className="font-medium">
            {hasConfiguredProvider 
              ? (currentProviderData?.name || 'Select Provider')
              : 'No models configured'
            }
          </span>
          {hasConfiguredProvider && (
            isCurrentProviderConfigured ? (
              <Check className="h-3 w-3 text-green-600" />
            ) : (
              <X className="h-3 w-3 text-muted-foreground" />
            )
          )}
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80" align="start" side="top">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-semibold text-sm mb-1">AI Provider</h4>
              <p className="text-xs text-muted-foreground">
                Select a provider and configure API keys
              </p>
            </div>
            {/* Provider selection buttons */}
            <div className="flex gap-1">
              {providers.map((provider) => {
                const isConfigured = configuredProviders[provider.id];
                const isSelected = selectedProvider === provider.id;
                
                return (
                  <button
                    key={provider.id}
                    onClick={() => handleProviderSelect(provider.id)}
                    disabled={!isConfigured}
                    title={`${provider.name}${!isConfigured ? ' - API key required' : ''}`}
                    className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : isConfigured
                        ? 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                        : 'bg-muted text-muted-foreground cursor-not-allowed opacity-50'
                    }`}
                  >
                    {provider.name}
                  </button>
                );
              })}
            </div>
          </div>

          {/* API Key Configuration */}
          <div className="border-t pt-3 space-y-3">
            <p className="text-xs font-medium">Configure API Keys</p>
            {providers.map((provider) => (
              <div key={provider.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor={`key-${provider.id}`} className="text-xs">
                    {provider.name}
                  </Label>
                  <a
                    href={provider.getKeyUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                  >
                    Get key
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                <div className="relative">
                  <Input
                    id={`key-${provider.id}`}
                    type={showKeys[provider.id] ? 'text' : 'password'}
                    placeholder={provider.apiKeyPlaceholder}
                    value={apiKeys[provider.id] || ''}
                    onChange={(e) => handleApiKeyChange(provider.id, e.target.value)}
                    className="pr-10 text-xs h-8"
                  />
                  <button
                    type="button"
                    onClick={() => toggleKeyVisibility(provider.id)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showKeys[provider.id] ? (
                      <EyeOff className="h-3.5 w-3.5" />
                    ) : (
                      <Eye className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>
              </div>
            ))}

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsOpen(false)}
                className="h-8"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSaveKeys}
                disabled={isSaving}
                className="h-8"
              >
                {isSaving ? 'Saving...' : 'Save Keys'}
              </Button>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

