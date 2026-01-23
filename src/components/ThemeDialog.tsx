'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
// import {
//   Select,
//   SelectContent,
//   SelectItem,
//   SelectTrigger,
//   SelectValue,
// } from '@/components/ui/select';
// } from '@/components/ui/select';
// import { StorageManager } from '@/lib/storage'; // Removed
import { useJunasContext } from '@/lib/context/JunasContext';
import { Moon, Sun, Minimize, Palette } from 'lucide-react';

interface ThemeDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ThemeDialog({ isOpen, onClose }: ThemeDialogProps) {
  const { settings, updateSettings } = useJunasContext();
  const [localTheme, setLocalTheme] = useState('vanilla');

  useEffect(() => {
    if (isOpen) {
      setLocalTheme(settings.theme || 'vanilla');
    }
  }, [isOpen, settings]);

  const handleSaveTheme = (isDark: boolean) => {
    updateSettings({
      ...settings,
      darkMode: isDark,
    });
  };

  const handleSaveFocusMode = (isFocus: boolean) => {
    updateSettings({
      ...settings,
      focusMode: isFocus,
    });
  };

  const handleThemeChange = (value: string) => {
    setLocalTheme(value);

    // Note: We might want to debounce this if it causes too many re-renders
    updateSettings({
      ...settings,
      theme: value as any,
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[400px] font-mono">
        <DialogHeader>
          <DialogTitle className="text-sm">[ Theme Settings ]</DialogTitle>
        </DialogHeader>

        <div className="py-4 space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="space-y-0.5">
                <Label htmlFor="theme" className="text-sm font-medium">Color Theme</Label>
                <p className="text-[10px] text-muted-foreground">
                  Select color palette
                </p>
              </div>
            </div>
            <Input
              value={localTheme}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleThemeChange(e.target.value)}
              className="w-[140px] h-8 text-xs font-mono"
              placeholder="vanilla"
            />
          </div>

          <div className="flex items-center justify-between border-t pt-4 border-muted-foreground/10">
            <div className="flex items-center gap-3">
              <div className="space-y-0.5">
                <Label htmlFor="darkMode" className="text-sm font-medium">Dark Mode</Label>
                <p className="text-[10px] text-muted-foreground">
                  {settings.darkMode ? 'Dark theme enabled' : 'Light theme enabled'}
                </p>
              </div>
            </div>
            <Switch
              id="darkMode"
              checked={settings.darkMode}
              onCheckedChange={handleSaveTheme}
            />
          </div>

          <div className="flex items-center justify-between border-t pt-4 border-muted-foreground/10">
            <div className="flex items-center gap-3">
              <div className="space-y-0.5">
                <Label htmlFor="focusMode" className="text-sm font-medium">Focus Mode</Label>
                <p className="text-[10px] text-muted-foreground">
                  {settings.focusMode ? 'UI elements hidden' : 'Standard UI view'}
                </p>
              </div>
            </div>
            <Switch
              id="focusMode"
              checked={settings.focusMode}
              onCheckedChange={handleSaveFocusMode}
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
