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
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center space-x-2">
            <Plus className="h-5 w-5" />
            <span>Start New Chat</span>
          </AlertDialogTitle>
          <AlertDialogDescription className="space-y-3">
            <p>
              This will clear your current conversation and start a fresh chat session.
            </p>
            <p className="font-semibold text-destructive">
              Warning: Your current conversation will be permanently deleted from your browser.
            </p>
            <div className="bg-muted p-3 rounded-md border border-border">
              <p className="text-sm font-medium text-foreground mb-1">
                Before you continue:
              </p>
              <p className="text-sm">
                Consider exporting your conversation to save it for future reference. You can export as JSON, Markdown, or plain text, and re-import it later to provide context to the AI.
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isLoading}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isLoading}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isLoading ? 'Starting...' : 'Start New Chat'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
