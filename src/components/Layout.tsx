'use client';

import { useState, useEffect } from 'react';
import { Plus, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ToastProvider } from '@/components/ui/toast';
import { migrateApiKeysToSession } from '@/lib/migrate-keys';

interface LayoutProps {
  children: React.ReactNode;
  onImport?: () => void;
  onNewChat?: () => void;
}

export function Layout({ children, onImport, onNewChat }: LayoutProps) {
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
          <div className="max-w-7xl mx-auto flex h-14 md:h-16 items-center gap-2 md:gap-6 px-3 md:px-6">
            {/* Left side - New Chat button */}
            <div className="flex items-center">
              {onNewChat && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onNewChat}
                  className="h-9 px-2 md:px-3"
                  data-tour="new-chat"
                >
                  <Plus className="h-4 w-4 md:mr-2" />
                  <span className="hidden md:inline">New Chat</span>
                </Button>
              )}
            </div>

            {/* Spacer */}
            <div className="flex-1"></div>

            {/* Right side controls */}
            <div className="flex items-center space-x-1 md:space-x-3">
              {/* Import button */}
              {onImport && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onImport}
                  className="h-9 px-2 md:px-3"
                  data-tour="import"
                >
                  <Upload className="h-4 w-4 md:mr-2" />
                  <span className="hidden lg:inline">Import</span>
                </Button>
              )}

            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 flex flex-col">
          {children}
        </main>

        {/* Footer */}
        <footer className="border-t bg-background py-4 px-6">
          <div className="max-w-7xl mx-auto text-center text-sm text-muted-foreground">
            <p>
              Made by{' '}
              <a
                href="https://gabrielongzm.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Gabriel Ong
              </a>
            </p>
            <p className="mt-1">
              Source code{' '}
              <a
                href="https://github.com/gongahkia/junas"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                here
              </a>
            </p>
          </div>
        </footer>
        </div>
      </ToastProvider>
  );
}

// Theme toggle removed; app is light-mode only for now.
