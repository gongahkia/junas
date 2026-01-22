"use client";
import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

const providers = [
  {
    id: "gemini",
    name: "Gemini",
    apiKeyPlaceholder: "Enter your Gemini API key",
    getKeyUrl: "https://aistudio.google.com/app/apikey",
  },
  {
    id: "openai",
    name: "OpenAI",
    apiKeyPlaceholder: "Enter your OpenAI API key",
    getKeyUrl: "https://platform.openai.com/api-keys",
  },
  {
    id: "claude",
    name: "Claude",
    apiKeyPlaceholder: "Enter your Anthropic API key",
    getKeyUrl: "https://console.anthropic.com/settings/keys",
  },
  {
    id: "ollama",
    name: "Ollama (Local)",
    apiKeyPlaceholder: "Enter Ollama Base URL (default: http://localhost:11434)",
    getKeyUrl: "https://ollama.com",
    isUrl: true,
  },
  {
    id: "lmstudio",
    name: "LM Studio (Local)",
    apiKeyPlaceholder: "Enter LM Studio Base URL (default: http://localhost:1234/v1)",
    getKeyUrl: "https://lmstudio.ai",
    isUrl: true,
  },
];

export function ProvidersTab() {
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [configuredProviders, setConfiguredProviders] = useState<Record<string, boolean>>({});
  const [providerHealth, setProviderHealth] = useState<Record<string, string>>({});

  useEffect(() => {
    checkConfiguredProviders();
    checkHealth();
  }, []);

  const checkConfiguredProviders = async () => {
    try {
      const response = await fetch("/api/auth/keys");
      if (response.ok) {
        const { configured, keys } = await response.json();
        setConfiguredProviders(configured);
        setApiKeys(keys || {});
      }
    } catch (error) {
      console.error("Error checking providers:", error);
    }
  };

  const checkHealth = async () => {
    try {
      const response = await fetch("/api/providers/health");
      if (response.ok) {
        const healthData = await response.json();
        setProviderHealth(healthData);
      }
    } catch (error) {
      console.error("Error checking health:", error);
    }
  };

  const handleApiKeyChange = (providerId: string, value: string) => {
    setApiKeys((prev) => ({ ...prev, [providerId]: value }));
  };

  const toggleKeyVisibility = (providerId: string) => {
    setShowKeys((prev) => ({ ...prev, [providerId]: !prev[providerId] }));
  };

  const handleSaveKeys = async () => {
    setIsSaving(true);
    try {
      const payload = {
        gemini: apiKeys.gemini,
        openai: apiKeys.openai,
        claude: apiKeys.claude,
        ollama: apiKeys.ollama,
        lmstudio: apiKeys.lmstudio,
      };
      const response = await fetch("/api/auth/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        await checkConfiguredProviders();
        await checkHealth();
      }
    } catch (error) {
      console.error("Error saving API keys:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const getHealthIndicator = (id: string) => {
    const status = providerHealth[id];
    if (status === 'online') return <div className="h-1.5 w-1.5 rounded-full bg-green-500" title="Online" />;
    if (status === 'offline') return <div className="h-1.5 w-1.5 rounded-full bg-red-500" title="Offline" />;
    return <div className="h-1.5 w-1.5 rounded-full bg-gray-400" title="Unconfigured" />;
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-muted-foreground">
          Select a provider and configure API keys
        </p>
      </div>
      <div className="pt-3 space-y-3">
        {providers.map((provider) => (
          <div key={provider.id} className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label htmlFor={`key-${provider.id}`} className="text-xs">
                  &gt; {provider.name}
                </Label>
                {getHealthIndicator(provider.id)}
              </div>
              <a
                href={provider.getKeyUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                {provider.isUrl ? 'Download' : 'Get key'}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <div className="relative">
              <Input
                id={`key-${provider.id}`}
                type={provider.isUrl || showKeys[provider.id] ? "text" : "password"}
                placeholder={provider.apiKeyPlaceholder}
                value={apiKeys[provider.id] || ""}
                onChange={(e) => handleApiKeyChange(provider.id, e.target.value)}
                className="pr-10 text-xs h-8 font-mono"
              />
              {!provider.isUrl && (
                <button
                  type="button"
                  onClick={() => toggleKeyVisibility(provider.id)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs font-mono"
                >
                  {showKeys[provider.id] ? "👁" : "•"}
                </button>
              )}
            </div>
          </div>
        ))}
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={handleSaveKeys}
            disabled={isSaving}
            className="px-3 py-1 text-xs bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            [ {isSaving ? "Saving..." : "Save"} ]
          </button>
        </div>
      </div>
    </div>
  );
}