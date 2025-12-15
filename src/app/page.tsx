'use client';

import { useState, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { NewChatDialog } from '@/components/chat/NewChatDialog';
import { ImportDialog } from '@/components/chat/ImportDialog';
import { StorageManager } from '@/lib/storage';
import { Message } from '@/types/chat';

export default function Home() {
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [chatKey, setChatKey] = useState(0); // Key to force re-render of ChatInterface
  const [messages, setMessages] = useState<Message[]>([]);

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
      hasMessages={hasMessages}
      onExport={handleExport}
      onImport={() => setShowImportDialog(true)}
      onNewChat={handleNewChat}
      onSearch={() => setShowSearchDialog(true)}
    >
      <ChatInterface
        key={chatKey}
        onMessagesChange={handleMessagesChange}
        scrollToMessageId={scrollToMessageId}
      />

      {/* New Chat Dialog */}
      <NewChatDialog
        isOpen={showNewChatDialog}
        onClose={() => setShowNewChatDialog(false)}
        onConfirm={handleConfirmNewChat}
      />

      {/* Export Dialog */}
      <ExportDialog
        isOpen={showExportDialog}
        onClose={() => setShowExportDialog(false)}
        messages={messages}
      />

      {/* Import Dialog */}
      <ImportDialog
        isOpen={showImportDialog}
        onClose={() => setShowImportDialog(false)}
        onImport={handleImport}
      />

      {/* Search Dialog */}
      <SearchDialog
        isOpen={showSearchDialog}
        onClose={() => setShowSearchDialog(false)}
        messages={messages}
        onMessageSelect={handleMessageSelect}
      />
    </Layout>
  );
}
