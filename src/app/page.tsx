import { useState, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { NewChatDialog } from '@/components/chat/NewChatDialog';
import { ShareDialog } from '@/components/chat/ShareDialog';
import { ConfigDialog } from '@/components/ConfigDialog';
import { AboutDialog } from '@/components/AboutDialog';
import { HistoryDialog } from '@/components/chat/HistoryDialog';
import { CommandPalette } from '@/components/chat/CommandPalette';
import { StorageManager } from '@/lib/storage';
import { Message, Conversation } from '@/types/chat';
import IntroAnimation from '@/components/IntroAnimation';

import { useJunasContext } from '@/lib/context/JunasContext';

export default function Home() {
  const { settings, chatState, updateChatState } = useJunasContext();

  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [showShareDialog, setShowShareDialog] = useState(false);
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showAboutDialog, setShowAboutDialog] = useState(false);
  const [showHistoryDialog, setShowHistoryDialog] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'chat' | 'artifacts' | 'tree'>('chat');

  const hasMessages = (chatState?.messages?.length || 0) > 0;
  const currentMessages = chatState?.messages || [];
  const currentNodeMap = chatState?.nodeMap || {};
  const currentLeafId = chatState?.currentLeafId;

  // Cleanup: Remove old event listeners logic as it is now handled by context and provider

  // Global Cmd/Ctrl+Shift+P listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const isCmdOrCtrl = isMac ? e.metaKey : e.ctrlKey;

      if (isCmdOrCtrl && e.shiftKey && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        setShowCommandPalette(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleNewChat = () => {
    setShowNewChatDialog(true);
  };

  const handleConfirmNewChat = () => {
    // Clear chat state via context
    updateChatState({
      messages: [],
      artifacts: [],
      isLoading: false,
      currentProvider: chatState?.currentProvider || 'gemini',
      settings: settings,
    });

    // Explicitly clear storage key if needed, though updateChatState handles standard saving
    StorageManager.clearChatState();

    // Close dialog
    setShowNewChatDialog(false);
  };

  const handleSelectConversation = (conversation: Conversation) => {
    // Load conversation into active state
    updateChatState({
      messages: conversation.messages,
      artifacts: conversation.artifacts || [],
      isLoading: false,
      currentProvider: 'gemini',
      settings: settings,
    });
  };

  if (loading) {
    return <IntroAnimation onComplete={() => setLoading(false)} />;
  }

  return (
    <div className="fade-in">
      <Layout
        focusMode={settings.focusMode}
        onShare={hasMessages ? () => setShowShareDialog(true) : undefined}
        onNewChat={handleNewChat}
        onCommandPalette={() => setShowCommandPalette(true)}
        onConfig={() => setShowConfigDialog(true)}
        onAbout={() => setShowAboutDialog(true)}
        onHistory={() => setShowHistoryDialog(true)}
      >
        <ChatInterface activeTab={activeTab} onTabChange={setActiveTab} />

        {/* New Chat Dialog */}
        <NewChatDialog
          isOpen={showNewChatDialog}
          onClose={() => setShowNewChatDialog(false)}
          onConfirm={handleConfirmNewChat}
        />

        {/* History Dialog */}
        <HistoryDialog
          isOpen={showHistoryDialog}
          onClose={() => setShowHistoryDialog(false)}
          onSelectConversation={handleSelectConversation}
        />

        {/* Share Dialog */}
        <ShareDialog
          isOpen={showShareDialog}
          onClose={() => setShowShareDialog(false)}
          messages={currentMessages}
          nodeMap={currentNodeMap}
          currentLeafId={currentLeafId}
        />

        {/* Config Dialog */}
        <ConfigDialog isOpen={showConfigDialog} onClose={() => setShowConfigDialog(false)} />

        {/* About Dialog */}
        <AboutDialog isOpen={showAboutDialog} onClose={() => setShowAboutDialog(false)} />

        {/* Command Palette */}
        <CommandPalette
          isOpen={showCommandPalette}
          onClose={() => setShowCommandPalette(false)}
          onOpenConfig={() => setShowConfigDialog(true)}
          onOpenShare={() => setShowShareDialog(true)}
          onOpenAbout={() => setShowAboutDialog(true)}
          onOpenHistory={() => setShowHistoryDialog(true)}
          onNewChat={hasMessages ? handleNewChat : undefined}
          onSwitchToChat={() => setActiveTab('chat')}
          onSwitchToArtifacts={() => setActiveTab('artifacts')}
          onSwitchToTree={() => setActiveTab('tree')}
          hasMessages={hasMessages}
        />
      </Layout>
    </div>
  );
}
