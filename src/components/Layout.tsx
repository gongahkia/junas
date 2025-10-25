'use client';

import { useState, useEffect } from 'react';
import { Moon, Sun, Settings, Download, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ToastProvider } from '@/components/ui/toast';
import { cn } from '@/lib/utils';

interface LayoutProps {
  children: React.ReactNode;
  hasMessages?: boolean;
  onExport?: () => void;
  onSettings?: () => void;
  onNewChat?: () => void;
}

export function Layout({ children, hasMessages = false, onExport, onSettings, onNewChat }: LayoutProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
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

              {/* Export button - only show when there are messages */}
              {onExport && (
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
