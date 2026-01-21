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
import { StorageManager } from '@/lib/storage';
import { Moon, Sun } from 'lucide-react';

interface ThemeDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ThemeDialog({ isOpen, onClose }: ThemeDialogProps) {
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const settings = StorageManager.getSettings();
      setDarkMode(settings.darkMode || false);
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
    
    // Dispatch theme change event
    window.dispatchEvent(new CustomEvent('junas-theme-change', { 
      detail: { darkMode: isDark } 
    }));
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[400px] font-mono">
        <DialogHeader>
          <DialogTitle className="text-sm">[ Theme Settings ]</DialogTitle>
        </DialogHeader>

        <div className="py-4 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-full ${darkMode ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'}`}>
                {darkMode ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
              </div>
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
        </div>
      </DialogContent>
    </Dialog>
  );
}
