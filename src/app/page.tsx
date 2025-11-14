'use client';

import { useState } from 'react';
import { Layout } from '@/components/Layout';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { ApiKeyModal } from '@/components/settings/ApiKeyModal';
import { NewChatDialog } from '@/components/chat/NewChatDialog';
import { ExportDialog } from '@/components/chat/ExportDialog';
import { ImportDialog } from '@/components/chat/ImportDialog';
import { SearchDialog } from '@/components/chat/SearchDialog';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ProviderSelector } from '@/components/settings/ProviderSelector';
import { UserSettings } from '@/components/settings/UserSettings';
import { StorageManager } from '@/lib/storage';
import { Message } from '@/types/chat';
import { LegalDisclaimerContent } from '@/components/LegalDisclaimer';

export default function Home() {
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [showSearchDialog, setShowSearchDialog] = useState(false);
  const [currentProvider, setCurrentProvider] = useState('gemini');
  const [chatKey, setChatKey] = useState(0); // Key to force re-render of ChatInterface
  const [messages, setMessages] = useState<Message[]>([]);
  const [scrollToMessageId, setScrollToMessageId] = useState<string | undefined>();

  const handleExport = () => {
    setShowExportDialog(true);
  };

  const handleImport = (importedMessages: Message[]) => {
    // Dispatch import event to ChatInterface
    const evt = new CustomEvent('junas-import', {
      detail: { messages: importedMessages }
    });
    window.dispatchEvent(evt);
  };

  const handleSettings = () => {
    setShowSettingsModal(true);
  };

  const handleProviderChange = (provider: string) => {
    setCurrentProvider(provider);
    // TODO: Save provider preference
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

  const handleMessagesChange = (newMessages: Message[]) => {
    setMessages(newMessages);
  };

  const handleMessageSelect = (messageId: string) => {
    setScrollToMessageId(messageId);
    // Reset after a short delay to allow future selections of the same message
    setTimeout(() => setScrollToMessageId(undefined), 100);
  };

  // Check if there are messages
  const hasMessages = messages.length > 0;

  return (
    <Layout
      hasMessages={hasMessages}
      onExport={handleExport}
      onImport={() => setShowImportDialog(true)}
      onSettings={handleSettings}
      onNewChat={handleNewChat}
      onSearch={() => setShowSearchDialog(true)}
    >
      <ChatInterface
        key={chatKey}
        onSettings={handleSettings}
        onMessagesChange={handleMessagesChange}
        scrollToMessageId={scrollToMessageId}
      />

      {/* API Key Modal */}
      <ApiKeyModal
        isOpen={showApiKeyModal}
        onClose={() => setShowApiKeyModal(false)}
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

      {/* Settings Modal */}
      <Dialog open={showSettingsModal} onOpenChange={setShowSettingsModal}>
        <DialogContent className="max-w-2xl max-h-[85vh] md:max-h-[80vh] overflow-y-auto w-[95vw] md:w-full">
          <DialogHeader>
            <DialogTitle className="text-base md:text-lg">Settings</DialogTitle>
            <DialogDescription className="text-xs md:text-sm">
              Configure your AI provider and application settings.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 md:space-y-6">
            {/* User Preferences */}
            <UserSettings />

            {/* Provider Selection */}
            <ProviderSelector
              currentProvider={currentProvider}
              onProviderChange={handleProviderChange}
            />

            {/* API Keys Section */}
            <Card>
              <CardHeader>
                <CardTitle>API Keys</CardTitle>
                <CardDescription>
                  Configure your API keys for different AI providers.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button onClick={() => setShowApiKeyModal(true)}>
                  Manage API Keys
                </Button>
              </CardContent>
            </Card>

            {/* App Info */}
            <Card>
              <CardHeader>
                <CardTitle>About Junas</CardTitle>
                <CardDescription>
                  Your AI legal assistant for Singapore law.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-sm text-muted-foreground">
                  <p>Version: 1.0.0</p>
                  <p>Built with Next.js 14 and TypeScript</p>
                  <p>Privacy-focused: All data stays in your browser</p>
                </div>
              </CardContent>
            </Card>

            {/* Legal Disclaimer */}
            <Card>
              <CardHeader>
                <CardTitle>Legal Disclaimer</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground">
                  <LegalDisclaimerContent />
                </div>
              </CardContent>
            </Card>
          </div>
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
