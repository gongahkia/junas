'use client';

import { useState, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { NewChatDialog } from '@/components/chat/NewChatDialog';
import { ImportDialog } from '@/components/chat/ImportDialog';
import { ProfileConfigDialog } from '@/components/ProfileConfigDialog';
import { StorageManager } from '@/lib/storage';
import { Message } from '@/types/chat';

export default function Home() {
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [chatKey, setChatKey] = useState(0); // Key to force re-render of ChatInterface

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

  return (
    <Layout
      onImport={() => setShowImportDialog(true)}
      onNewChat={handleNewChat}
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

      {/* Profile Config Dialog */}
      <ProfileConfigDialog
        isOpen={showConfigDialog}
        onClose={() => setShowConfigDialog(false)}
      />
    </Layout>
  );
}
