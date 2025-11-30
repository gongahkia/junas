"use client";

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Settings, Eye, EyeOff, ExternalLink } from 'lucide-react';

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

  // Load configured providers status on mount
  useEffect(() => {
    checkConfiguredProviders();
  }, []);

  const checkConfiguredProviders = async () => {
    try {
      const response = await fetch('/api/auth/keys');
      if (response.ok) {
        const { configured } = await response.json();
        setConfiguredProviders(configured);

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
    setSelectedProvider(providerId);
    onProviderChange(providerId);
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
      const response = await fetch('/api/auth/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apiKeys }),
      });

      if (response.ok) {
        // Refresh configured status
        await checkConfiguredProviders();
        // Clear local state
        setApiKeys({});
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

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">Provider:</span>

      <Select value={selectedProvider} onValueChange={handleProviderSelect}>
        <SelectTrigger className="w-[140px] h-8">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {providers.map((provider) => (
            <SelectItem key={provider.id} value={provider.id}>
              <div className="flex items-center gap-2">
                {provider.name}
                {configuredProviders[provider.id] && (
                  <span className="text-xs text-green-600">✓</span>
                )}
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-2">
            <Settings className="h-3.5 w-3.5" />
            {hasConfiguredProvider ? 'Manage Keys' : 'Add API Key'}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-96" align="end">
          <div className="space-y-4">
            <div>
              <h4 className="font-semibold text-sm mb-1">API Keys</h4>
              <p className="text-xs text-muted-foreground">
                Configure your API keys to use different providers
              </p>
            </div>

            {providers.map((provider) => (
              <div key={provider.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor={`key-${provider.id}`} className="text-sm">
                    {provider.name}
                    {configuredProviders[provider.id] && (
                      <span className="ml-2 text-xs text-green-600">Configured</span>
                    )}
                  </Label>
                  <a
                    href={provider.getKeyUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                  >
                    Get API key
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
                    className="pr-10 text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => toggleKeyVisibility(provider.id)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showKeys[provider.id] ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
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
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSaveKeys}
                disabled={isSaving || Object.keys(apiKeys).length === 0}
              >
                {isSaving ? 'Saving...' : 'Save Keys'}
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
