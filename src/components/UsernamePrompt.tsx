"use client";

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { StorageManager } from '@/lib/storage';

export function UsernamePrompt() {
  const [isOpen, setIsOpen] = useState(false);
  const [username, setUsername] = useState('');

  useEffect(() => {
    // Check if user has seen disclaimer and has no username set
    const hasSeenDisclaimer = StorageManager.hasSeenDisclaimer();
    const settings = StorageManager.getSettings();

    if (hasSeenDisclaimer && !settings.userName) {
      setIsOpen(true);
    }
  }, []);

  const handleSave = () => {
    if (username.trim()) {
      const settings = StorageManager.getSettings();
      StorageManager.saveSettings({
        ...settings,
        userName: username.trim(),
      });
    }
    setIsOpen(false);
  };

  const handleSkip = () => {
    // Set a placeholder to prevent showing again
    const settings = StorageManager.getSettings();
    StorageManager.saveSettings({
      ...settings,
      userName: 'User',
    });
    setIsOpen(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={() => {}}>
      <DialogContent
        className="sm:max-w-[400px]"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>Welcome to Junas!</DialogTitle>
          <DialogDescription>
            What should I call you? This helps personalize your experience.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <Label htmlFor="username" className="text-sm font-medium">
            Your Name (Optional)
          </Label>
          <Input
            id="username"
            type="text"
            placeholder="Enter your name"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSave();
              }
            }}
            className="mt-2"
            autoFocus
          />
        </div>

        <DialogFooter className="flex gap-2">
          <Button variant="outline" onClick={handleSkip}>
            Skip
          </Button>
          <Button onClick={handleSave} disabled={!username.trim()}>
            Continue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
