"use client";
import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ExternalLink } from "lucide-react";

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
];

export function ProvidersTab() {
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [configuredProviders, setConfiguredProviders] = useState<Record<string, boolean>>({});

  useEffect(() => {
    checkConfiguredProviders();
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
      };
      const response = await fetch("/api/auth/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        await checkConfiguredProviders();
      }
    } catch (error) {
      console.error("Error saving API keys:", error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-muted-foreground">
          Select a provider and configure API keys
        </p>
      </div>
      <div className="pt-3 space-y-3">
        <p className="text-xs font-medium">&gt; Configure API Keys</p>
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
                type={showKeys[provider.id] ? "text" : "password"}
                placeholder={provider.apiKeyPlaceholder}
                value={apiKeys[provider.id] || ""}
                onChange={(e) => handleApiKeyChange(provider.id, e.target.value)}
                className="pr-10 text-xs h-8 font-mono"
              />
              <button
                type="button"
                onClick={() => toggleKeyVisibility(provider.id)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs font-mono"
              >
                {showKeys[provider.id] ? "👁" : "•"}
              </button>
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