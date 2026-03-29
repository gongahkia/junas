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
import { OnboardingWizard } from '@/components/OnboardingWizard';
import { TemplateLibrary } from '@/components/TemplateLibrary';
import { ComplianceDashboard } from '@/components/ComplianceDashboard';
import { ClauseLibrary } from '@/components/ClauseLibrary';
import { RedlineView } from '@/components/chat/RedlineView';

import { useJunasContext } from '@/lib/context/JunasContext';

export default function Home() {
  const { settings, chatState, updateChatState } = useJunasContext();

  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [showShareDialog, setShowShareDialog] = useState(false);
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showAboutDialog, setShowAboutDialog] = useState(false);
  const [showHistoryDialog, setShowHistoryDialog] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [showTemplateLibrary, setShowTemplateLibrary] = useState(false);
  const [showComplianceDashboard, setShowComplianceDashboard] = useState(false);
  const [showClauseLibrary, setShowClauseLibrary] = useState(false);
  const [showRedline, setShowRedline] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(
    () => !StorageManager.hasCompletedOnboarding()
  );
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'chat' | 'artifacts' | 'tree'>('chat');

  const hasMessages = (chatState?.messages?.length || 0) > 0;
  const currentMessages = chatState?.messages || [];
  const currentNodeMap = chatState?.nodeMap || {};
  const currentLeafId = chatState?.currentLeafId;

  // Cleanup: Remove old event listeners logic as it is now handled by context and provider

  // Listen for command events that open dialogs
  useEffect(() => {
    const openTemplates = () => setShowTemplateLibrary(true);
    const openRedline = () => setShowRedline(true);
    const openCompliance = () => setShowComplianceDashboard(true);
    const openClauses = () => setShowClauseLibrary(true);
    window.addEventListener('junas-open-templates', openTemplates);
    window.addEventListener('junas-open-redline', openRedline);
    window.addEventListener('junas-open-compliance', openCompliance);
    window.addEventListener('junas-open-clauses', openClauses);
    return () => {
      window.removeEventListener('junas-open-templates', openTemplates);
      window.removeEventListener('junas-open-redline', openRedline);
      window.removeEventListener('junas-open-compliance', openCompliance);
      window.removeEventListener('junas-open-clauses', openClauses);
    };
  }, []);

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

        {/* Template Library */}
        <TemplateLibrary
          isOpen={showTemplateLibrary}
          onClose={() => setShowTemplateLibrary(false)}
          onGenerate={(content, title) => {
            const artifacts = chatState?.artifacts || [];
            updateChatState({
              ...chatState,
              artifacts: [
                { id: `tpl_${Date.now()}`, title, type: 'markdown', content, createdAt: Date.now() },
                ...artifacts,
              ],
            });
            setActiveTab('artifacts');
          }}
        />

        {/* Compliance Dashboard */}
        <ComplianceDashboard
          isOpen={showComplianceDashboard}
          onClose={() => setShowComplianceDashboard(false)}
        />

        {/* Clause Library */}
        <ClauseLibrary
          isOpen={showClauseLibrary}
          onClose={() => setShowClauseLibrary(false)}
        />

        {/* Redline View */}
        {showRedline && (
          <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-8">
            <div className="bg-background border rounded-lg shadow-lg w-full max-w-4xl max-h-[80vh] overflow-y-auto p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-sm font-semibold">Contract Redlining</h2>
                <button onClick={() => setShowRedline(false)} className="text-xs text-muted-foreground hover:text-foreground">
                  [ Close ]
                </button>
              </div>
              <RedlineView />
            </div>
          </div>
        )}

        {/* Onboarding Wizard */}
        <OnboardingWizard
          open={showOnboarding}
          onComplete={() => setShowOnboarding(false)}
          onOpenConfig={() => {
            setShowOnboarding(false);
            setShowConfigDialog(true);
          }}
        />
      </Layout>
    </div>
  );
}
