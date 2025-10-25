'use client';

import { useState } from 'react';
import { Layout } from '@/components/Layout';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { ApiKeyModal } from '@/components/settings/ApiKeyModal';
import { NewChatDialog } from '@/components/chat/NewChatDialog';
import { ExportButton } from '@/components/chat/ExportButton';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ProviderSelector } from '@/components/settings/ProviderSelector';
import { StorageManager } from '@/lib/storage';

export default function Home() {
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [currentProvider, setCurrentProvider] = useState('gemini');
  const [chatKey, setChatKey] = useState(0); // Key to force re-render of ChatInterface

  const handleExport = () => {
    // Proxy to ChatInterface export via custom event
    const evt = new CustomEvent('junas-export');
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

  // Check if there are messages in localStorage
  const hasMessages = typeof window !== 'undefined' && StorageManager.getChatState()?.messages?.length > 0;

  return (
    <Layout
      hasMessages={hasMessages}
      onExport={handleExport}
      onSettings={handleSettings}
      onNewChat={handleNewChat}
    >
      <ChatInterface
        key={chatKey}
        onSettings={handleSettings}
        onExport={handleExport}
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

      {/* Settings Modal */}
      <Dialog open={showSettingsModal} onOpenChange={setShowSettingsModal}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Settings</DialogTitle>
            <DialogDescription>
              Configure your AI provider and application settings.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
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
              <CardContent className="space-y-2">
                <div className="text-sm text-muted-foreground">
                  <p>Version: 1.0.0</p>
                  <p>Built with Next.js 14 and TypeScript</p>
                  <p>Privacy-focused: All data stays in your browser</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
