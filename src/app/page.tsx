'use client';

import { useState, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { NewChatDialog } from '@/components/chat/NewChatDialog';
import { ImportDialog } from '@/components/chat/ImportDialog';
import { ExportDialog } from '@/components/chat/ExportDialog';
import { ConfigDialog } from '@/components/ConfigDialog';
import { StorageManager } from '@/lib/storage';
import { Message } from '@/types/chat';
import IntroAnimation from '@/components/IntroAnimation';

export default function Home() {
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [chatKey, setChatKey] = useState(0); // Key to force re-render of ChatInterface
  const [hasMessages, setHasMessages] = useState(false);
  const [currentMessages, setCurrentMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);

  // Check if there are messages on mount and update periodically
  useEffect(() => {
    const checkMessages = () => {
      const chatState = StorageManager.getChatState();
      const messages = chatState?.messages || [];
      setHasMessages(messages.length > 0);
      setCurrentMessages(messages);
    };

    checkMessages();

    // Check every second for message changes
    const interval = setInterval(checkMessages, 1000);
    return () => clearInterval(interval);
  }, [chatKey]);

  const handleImport = (importedMessages: Message[]) => {
    // Dispatch import event to ChatInterface
    const evt = new CustomEvent('junas-import', {
      detail: { messages: importedMessages }
    });
    window.dispatchEvent(evt);
  };

  const handleNewChat = () => {
    setShowNewChatDialog(true);
  };

  const handleConfirmNewChat = () => {
    // Clear chat state from localStorage
    StorageManager.clearChatState();

    // Force re-render of ChatInterface by changing key
    setChatKey(prev => prev + 1);

    // Close dialog
    setShowNewChatDialog(false);
  };

  if (loading) {
    return <IntroAnimation onComplete={() => setLoading(false)} />;
  }

  return (
    <div className="fade-in">
      <Layout
        onImport={!hasMessages ? () => setShowImportDialog(true) : undefined}
        onExport={hasMessages ? () => setShowExportDialog(true) : undefined}
        onNewChat={hasMessages ? handleNewChat : undefined}
        onConfig={() => setShowConfigDialog(true)}
      >
        <ChatInterface key={chatKey} />

        {/* New Chat Dialog */}
        <NewChatDialog
          isOpen={showNewChatDialog}
          onClose={() => setShowNewChatDialog(false)}
          onConfirm={handleConfirmNewChat}
        />

        {/* Import Dialog */}
        <ImportDialog
          isOpen={showImportDialog}
          onClose={() => setShowImportDialog(false)}
          onImport={handleImport}
        />

        {/* Export Dialog */}
        <ExportDialog
          isOpen={showExportDialog}
          onClose={() => setShowExportDialog(false)}
          messages={currentMessages}
        />

        {/* Config Dialog */}
        <ConfigDialog
          isOpen={showConfigDialog}
          onClose={() => setShowConfigDialog(false)}
        />
      </Layout>
    </div>
  );
}
