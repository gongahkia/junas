'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { StorageManager } from '@/lib/storage';
import { Brain, Sparkles, Info } from 'lucide-react';

export function ReasoningSettings() {
  const [settings, setSettings] = useState(() => StorageManager.getSettings());

  const updateSetting = (key: keyof typeof settings, value: any) => {
    const newSettings = { ...settings, [key]: value };
    setSettings(newSettings);
    StorageManager.saveSettings(newSettings);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-primary" />
          <CardTitle>Advanced Reasoning</CardTitle>
        </div>
        <CardDescription>
          Configure deep thinking and multi-stage reasoning for complex legal queries
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Enable Advanced Reasoning */}
        <div className="flex items-center justify-between space-x-2">
          <div className="flex-1 space-y-1">
            <div className="flex items-center gap-2">
              <Label htmlFor="advanced-reasoning">Enable Advanced Reasoning</Label>
              <Sparkles className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="text-sm text-muted-foreground">
              Automatically use multi-stage reasoning and self-critique for complex queries
            </p>
          </div>
          <Switch
            id="advanced-reasoning"
            checked={settings.enableAdvancedReasoning}
            onCheckedChange={(checked) => updateSetting('enableAdvancedReasoning', checked)}
          />
        </div>

        {/* Default Reasoning Depth */}
        <div className="space-y-2">
          <Label htmlFor="reasoning-depth" className="pl-0">Default Reasoning Depth</Label>
          <Select
            value={settings.defaultReasoningDepth}
            onValueChange={(value) => updateSetting('defaultReasoningDepth', value)}
            disabled={!settings.enableAdvancedReasoning}
          >
            <SelectTrigger id="reasoning-depth" className="pl-3">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="quick">
                <div>
                  <div className="font-medium">Quick</div>
                  <div className="text-xs text-muted-foreground">Fast responses, basic reasoning</div>
                </div>
              </SelectItem>
              <SelectItem value="standard">
                <div>
                  <div className="font-medium">Standard</div>
                  <div className="text-xs text-muted-foreground">Balanced speed and depth</div>
                </div>
              </SelectItem>
              <SelectItem value="deep">
                <div>
                  <div className="font-medium">Deep</div>
                  <div className="text-xs text-muted-foreground">Multi-step analysis with self-critique</div>
                </div>
              </SelectItem>
              <SelectItem value="expert">
                <div>
                  <div className="font-medium">Expert</div>
                  <div className="text-xs text-muted-foreground">Maximum depth with ReAct pattern</div>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground pl-0">
            Junas automatically adjusts reasoning depth based on query complexity
          </p>
        </div>

        {/* Show Reasoning Stages */}
        <div className="flex items-center justify-between space-x-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="show-stages">Show Reasoning Stages</Label>
            <p className="text-sm text-muted-foreground">
              Display intermediate reasoning steps for multi-stage analysis
            </p>
          </div>
          <Switch
            id="show-stages"
            checked={settings.showReasoningStages}
            onCheckedChange={(checked) => updateSetting('showReasoningStages', checked)}
            disabled={!settings.enableAdvancedReasoning}
          />
        </div>

        {/* Info Box */}
        <div className="rounded-lg border bg-muted/50 p-4">
          <div className="flex gap-3">
            <Info className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
            <div className="space-y-2 text-sm">
              <p className="font-medium">How Advanced Reasoning Works</p>
              <ul className="space-y-1 text-muted-foreground">
                <li>• <strong>Chain-of-Thought:</strong> Step-by-step legal analysis</li>
                <li>• <strong>Self-Critique:</strong> Reviews and improves initial analysis</li>
                <li>• <strong>ReAct Pattern:</strong> Iterative reasoning for expert queries</li>
                <li>• <strong>Auto-Classification:</strong> Complexity detection adjusts depth automatically</li>
              </ul>
              <p className="text-xs pt-2">
                Provider-agnostic: Works with Claude, Gemini, and OpenAI
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
