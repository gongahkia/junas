import { useState, useEffect } from 'react';
import { COMMANDS, CommandInfo } from '@/lib/commands/command-processor';
import { Switch } from '@/components/ui/switch';
import { StorageManager } from '@/lib/storage';
import { Info } from 'lucide-react';

export function ToolsTab() {
  const [disabledTools, setDisabledTools] = useState<string[]>([]);

  useEffect(() => {
    // In a real app, this would come from storage. 
    // For now, let's assume we store it in local storage similar to other settings
    const stored = localStorage.getItem('junas_disabled_tools');
    if (stored) {
      setDisabledTools(JSON.parse(stored));
    }
  }, []);

  const toggleTool = (toolId: string) => {
    setDisabledTools(prev => {
      const next = prev.includes(toolId) 
        ? prev.filter(id => id !== toolId)
        : [...prev, toolId];
      
      localStorage.setItem('junas_disabled_tools', JSON.stringify(next));
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <div className="text-xs text-muted-foreground space-y-1">
        <p>Enable or disable specific tools available to the AI Agent.</p>
        <p>Disabling tools can prevent the AI from taking certain actions.</p>
      </div>

      <div className="space-y-3">
        {COMMANDS.map((cmd) => (
          <div key={cmd.id} className="flex items-center justify-between border border-muted-foreground/20 p-3 rounded-sm">
            <div className="flex-1 mr-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-sm font-medium">/{cmd.id}</span>
                {cmd.isLocal && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-green-500/10 text-green-600 rounded">
                    LOCAL
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{cmd.description}</p>
            </div>
            <Switch 
              checked={!disabledTools.includes(cmd.id)}
              onCheckedChange={() => toggleTool(cmd.id)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
