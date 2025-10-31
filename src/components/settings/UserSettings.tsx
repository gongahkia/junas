'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { StorageManager } from '@/lib/storage';
import { User } from 'lucide-react';

export function UserSettings() {
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
          <User className="h-5 w-5 text-muted-foreground" />
          <CardTitle>User Preferences</CardTitle>
        </div>
        <CardDescription>
          Personalize your experience with Junas
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="user-name">Your Name (Optional)</Label>
          <Input
            id="user-name"
            type="text"
            placeholder="Enter your name"
            value={settings.userName || ''}
            onChange={(e) => updateSetting('userName', e.target.value)}
            className="max-w-md"
          />
          <p className="text-xs text-muted-foreground">
            Junas will greet you by name when you start a conversation
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
