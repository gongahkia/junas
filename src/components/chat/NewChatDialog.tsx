'use client';

import { useState } from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';

interface NewChatDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function NewChatDialog({ isOpen, onClose, onConfirm }: NewChatDialogProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleConfirm = async () => {
    setIsLoading(true);
    try {
      await onConfirm();
      onClose();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent className="font-mono">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-sm">
            [ + Start New Chat ]
          </AlertDialogTitle>
          <AlertDialogDescription className="text-xs">
            This will clear your current conversation and start a fresh chat session.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-3 text-xs">
          <div className="font-semibold text-destructive">
            ! Warning: Your current conversation will be permanently deleted from your browser.
          </div>
          <div className="bg-muted/30 p-3 border border-muted-foreground/30">
            <div className="font-medium mb-1">
              &gt; Before you continue:
            </div>
            <div className="text-muted-foreground">
              Consider exporting your conversation to save it for future reference. You can export as JSON, Markdown, or plain text, and re-import it later to provide context to the AI.
            </div>
          </div>
        </div>
        <AlertDialogFooter>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="px-3 py-2 text-xs hover:bg-muted transition-colors disabled:opacity-50"
          >
            [ Cancel ]
          </button>
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            className="px-3 py-2 text-xs bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50"
          >
            [ {isLoading ? 'Starting...' : 'Start New Chat'} ]
          </button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
