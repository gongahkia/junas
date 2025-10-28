'use client';

import { useState, useEffect } from 'react';
import { Settings, Download, Plus, Upload, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ToastProvider } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import { migrateApiKeysToSession } from '@/lib/migrate-keys';

interface LayoutProps {
  children: React.ReactNode;
  hasMessages?: boolean;
  onExport?: () => void;
  onImport?: () => void;
  onSettings?: () => void;
  onNewChat?: () => void;
  onSearch?: () => void;
}

export function Layout({ children, hasMessages = false, onExport, onImport, onSettings, onNewChat, onSearch }: LayoutProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);

    // Migrate old localStorage API keys to secure session storage
    migrateApiKeysToSession().catch((error) => {
      console.error('Failed to migrate API keys:', error);
    });
  }, []);

  if (!mounted) {
    return null;
  }

  return (
      <ToastProvider>
        <div className="min-h-screen bg-background flex flex-col">
        {/* Header */}
        <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="max-w-7xl mx-auto flex h-16 items-center justify-between px-6">
            {/* Left side intentionally minimal (brand hidden) */}
            <div />

            {/* Right side controls */}
            <div className="flex items-center space-x-3">
              {/* New Chat button */}
              {onNewChat && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onNewChat}
                  className="h-9 px-3"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  New Chat
                </Button>
              )}

              {/* Search button - only show when there are messages */}
              {onSearch && hasMessages && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onSearch}
                  className="h-9 px-3"
                >
                  <Search className="h-4 w-4 mr-2" />
                  Search
                </Button>
              )}

              {/* Import button */}
              {onImport && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onImport}
                  className="h-9 px-3"
                >
                  <Upload className="h-4 w-4 mr-2" />
                  Import
                </Button>
              )}

              {/* Export button - only show when there are messages */}
              {onExport && hasMessages && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onExport}
                  className="h-9 px-3"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </Button>
              )}

              {/* Settings button */}
              {onSettings && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onSettings}
                  className="h-9 px-3"
                >
                  <Settings className="h-4 w-4 mr-2" />
                  Settings
                </Button>
              )}

            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 flex flex-col">
          {children}
        </main>
        </div>
      </ToastProvider>
  );
}

// Theme toggle removed; app is light-mode only for now.
