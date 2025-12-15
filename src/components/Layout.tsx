'use client';

import { useState, useEffect } from 'react';
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
          <div className="max-w-7xl mx-auto flex h-14 md:h-16 items-center gap-2 md:gap-6 px-4 md:px-8 font-mono">
            {/* Left side - New Chat button */}
            <div className="flex items-center">
              {onNewChat && (
                <button
                  onClick={onNewChat}
                  className="px-2 py-1 text-xs md:text-sm hover:bg-muted transition-colors"
                  data-tour="new-chat"
                >
                  [ + New Chat ]
                </button>
              )}
            </div>

            {/* Spacer */}
            <div className="flex-1"></div>

            {/* Right side controls */}
            <div className="flex items-center space-x-2 md:space-x-4">
              {/* Import button */}
              {onImport && (
                <button
                  onClick={onImport}
                  className="px-2 py-1 text-xs md:text-sm hover:bg-muted transition-colors"
                  data-tour="import"
                >
                  [ ↑ Import ]
                </button>
              )}
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 flex flex-col">
          {children}
        </main>

        {/* Footer */}
        <footer className="border-t bg-background py-3 md:py-4 px-4 md:px-8">
          <div className="max-w-7xl mx-auto text-center text-xs md:text-sm text-muted-foreground font-mono">
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
              {' | '}
              <a
                href="https://github.com/gongahkia/junas"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Source
              </a>
            </p>
          </div>
        </footer>
        </div>
      </ToastProvider>
  );
}

// Theme toggle removed; app is light-mode only for now.
