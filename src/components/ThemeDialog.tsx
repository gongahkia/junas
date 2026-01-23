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
import { StorageManager } from '@/lib/storage';
import { Moon, Sun, Minimize, Palette } from 'lucide-react';

interface ThemeDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ThemeDialog({ isOpen, onClose }: ThemeDialogProps) {
  const [darkMode, setDarkMode] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [theme, setTheme] = useState('vanilla');

  useEffect(() => {
    if (isOpen) {
      const settings = StorageManager.getSettings();
      setDarkMode(settings.darkMode || false);
      setFocusMode(settings.focusMode || false);
      setTheme(settings.theme || 'vanilla');
    }
  }, [isOpen]);

  const handleSaveTheme = (isDark: boolean) => {
    setDarkMode(isDark);

    // Save settings
    const settings = StorageManager.getSettings();
    StorageManager.saveSettings({
      ...settings,
      darkMode: isDark,
    });

    // Dispatch theme change event (handled by page.tsx)
    window.dispatchEvent(new CustomEvent('junas-theme-change', {
      detail: { darkMode: isDark, theme: theme }
    }));
  };

  const handleSaveFocusMode = (isFocus: boolean) => {
    setFocusMode(isFocus);

    // Save settings
    const settings = StorageManager.getSettings();
    StorageManager.saveSettings({
      ...settings,
      focusMode: isFocus,
    });
  };

  const handleThemeChange = (value: string) => {
    setTheme(value);

    // Save settings
    const settings = StorageManager.getSettings();
    StorageManager.saveSettings({
      ...settings,
      theme: value as any,
    });

    // Dispatch theme change event
    window.dispatchEvent(new CustomEvent('junas-theme-change', {
      detail: { darkMode, theme: value }
    }));
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
                <Label htmlFor="darkMode" className="text-sm font-medium">Dark Mode</Label>
                <p className="text-[10px] text-muted-foreground">
                  {darkMode ? 'Dark theme enabled' : 'Light theme enabled'}
                </p>
              </div>
            </div>
            <Switch
              id="darkMode"
              checked={darkMode}
              onCheckedChange={handleSaveTheme}
            />
          </div>

          <div className="flex items-center justify-between border-t pt-4 border-muted-foreground/10">
            <div className="flex items-center gap-3">
              <div className="space-y-0.5">
                <Label htmlFor="theme" className="text-sm font-medium">Color Theme</Label>
                <p className="text-[10px] text-muted-foreground">
                  Select color palette
                </p>
              </div>
            </div>
            <Input
              value={theme}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleThemeChange(e.target.value)}
              className="w-[140px] h-8 text-xs font-mono"
              placeholder="vanilla"
            />
            {/* <Select value={theme} onValueChange={handleThemeChange}>
              <SelectTrigger className="w-[140px] h-8 text-xs">
                <SelectValue placeholder="Select theme" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="vanilla">Vanilla (B&W)</SelectItem>
                <SelectItem value="gruvbox">Gruvbox</SelectItem>
                <SelectItem value="everforest">Everforest</SelectItem>
                <SelectItem value="tokyo-night">Tokyo Night</SelectItem>
                <SelectItem value="catppuccin">Catppuccin</SelectItem>
                <SelectItem value="solarized">Solarized</SelectItem>
                <SelectItem value="rose-pine">Rose Pine</SelectItem>
                <SelectItem value="kanagawa">Kanagawa</SelectItem>
              </SelectContent>
            </Select> */}
          </div>

          <div className="flex items-center justify-between border-t pt-4 border-muted-foreground/10">
            <div className="flex items-center gap-3">
              <div className="space-y-0.5">
                <Label htmlFor="focusMode" className="text-sm font-medium">Focus Mode</Label>
                <p className="text-[10px] text-muted-foreground">
                  {focusMode ? 'UI elements hidden' : 'Standard UI view'}
                </p>
              </div>
            </div>
            <Switch
              id="focusMode"
              checked={focusMode}
              onCheckedChange={handleSaveFocusMode}
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
