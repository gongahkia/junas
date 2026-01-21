'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Message } from '@/types/chat';
import { decompressChat } from '@/lib/share-utils';
import { MessageList } from '@/components/chat/MessageList';
import { Button } from '@/components/ui/button';
import { StorageManager } from '@/lib/storage';
import { JUNAS_ASCII_LOGO } from '@/lib/constants';
import { useToast, ToastProvider } from '@/components/ui/toast';
import { Download } from 'lucide-react';
import { Layout } from '@/components/Layout';

function SharePageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isValid, setIsValid] = useState(false);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    const data = searchParams.get('d');
    if (data) {
      try {
        const decompressed = decompressChat(data);
        if (decompressed && decompressed.length > 0) {
          setMessages(decompressed);
          setIsValid(true);
        } else {
          setIsValid(false);
        }
      } catch (e) {
        console.error('Failed to parse share data', e);
        setIsValid(false);
      }
    }
    setLoading(false);
  }, [searchParams]);

  const handleImport = () => {
    if (messages.length > 0) {
      // Confirm if user wants to overwrite if there are existing messages?
      // For simplicity, we'll just save it as the current conversation context.
      // If the user already has a chat, this might be destructive if we just use `saveChatState`.
      // A safer approach: Load these messages into the chat state.
      
      const currentChat = StorageManager.getChatState();
      
      if (currentChat && currentChat.messages.length > 0) {
        const confirmed = window.confirm('Importing this chat will replace your current active conversation. Do you want to proceed?');
        if (!confirmed) return;
      }

      StorageManager.saveChatState({
        messages: messages,
        isLoading: false,
        currentProvider: currentChat?.currentProvider || 'gemini', // Default or keep existing
        apiKeys: StorageManager.getApiKeys(), // Keep existing keys
        settings: StorageManager.getSettings(), // Keep existing settings
      });

      router.push('/');
      addToast({
        type: 'success',
        title: 'Chat Imported',
        description: 'You can now continue the conversation.',
      });
    }
  };

  const handleCopyMessage = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      addToast({
        type: 'success',
        title: 'Copied',
        description: 'Message copied to clipboard',
      });
    } catch {
      addToast({
        type: 'error',
        title: 'Error',
        description: 'Failed to copy',
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-muted-foreground font-mono text-sm">[ Loading shared chat... ]</div>
      </div>
    );
  }

  if (!isValid) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen space-y-4 text-center px-4">
        <div className="p-4 rounded-full bg-destructive/10 text-destructive">
          <Download className="w-8 h-8" />
        </div>
        <h1 className="text-xl font-bold font-mono">Invalid or Expired Link</h1>
        <p className="text-muted-foreground max-w-md font-mono text-sm">
          The shared link appears to be invalid or corrupted. Please ask the sender to generate a new link.
        </p>
        <Button onClick={() => router.push('/')} variant="outline" className="font-mono text-xs">
          [ Return Home ]
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur px-4 md:px-8 py-3 flex items-center justify-between">
        <div className="font-mono text-sm font-semibold">
          [ Shared Conversation ]
        </div>
        <div className="flex items-center gap-4">
           <Button 
            onClick={handleImport} 
            size="sm" 
            className="font-mono text-xs"
          >
            [ Import & Continue ]
          </Button>
        </div>
      </header>
      
      <main className="flex-1 overflow-hidden flex flex-col relative">
        <MessageList 
          messages={messages} 
          isLoading={false} 
          onCopyMessage={handleCopyMessage}
          onRegenerateMessage={() => {}} // No-op for read-only
        />
        
        {/* Overlay to indicate read-only state at the bottom */}
        <div className="absolute bottom-0 w-full p-4 bg-gradient-to-t from-background to-transparent pointer-events-none flex justify-center pb-8">
           <div className="px-4 py-2 bg-muted/80 backdrop-blur rounded-full text-xs font-mono text-muted-foreground border shadow-sm pointer-events-auto">
             Read-only mode. Click "Import & Continue" to chat.
           </div>
        </div>
      </main>
    </div>
  );
}

export default function SharePage() {
  return (
    <Suspense fallback={<div className="p-8 font-mono text-sm">[ Loading... ]</div>}>
      <ToastProvider>
        <SharePageContent />
      </ToastProvider>
    </Suspense>
  );
}
