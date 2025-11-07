'use client';

import { useState, useEffect, useCallback } from 'react';
import { Message, ReasoningMetadata, ThinkingStage, Conversation } from '@/types/chat';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { HeroMarquee } from './HeroMarquee';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';
import { TemplateSelector } from './TemplateSelector';
import { TemplateForm } from './TemplateForm';
import { ReasoningProgress } from './ReasoningIndicator';
import { StorageManager } from '@/lib/storage';
import { ChatService } from '@/lib/ai/chat-service';
import { extractAndLookupCitations } from '@/lib/tools/citation-extractor';
import { exportToBibTeX, exportToEndNote, exportToZotero, downloadCitationFile } from '@/lib/citation-export';
import { useToast } from '@/components/ui/toast';
import { generateId } from '@/lib/utils';
import { extractTemplateFields, type LegalTemplate, type TemplateField } from '@/lib/templates';
import { ConversationSwitcher } from '@/components/chat/ConversationSwitcher';
import { ChatSearch } from '@/components/chat/ChatSearch';
import { CitationManager } from '@/components/chat/CitationManager';
import { ReasoningProgressBar } from '@/components/chat/ReasoningProgressBar';
import { Button } from '@/components/ui/button';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

interface ChatInterfaceProps {
  onSettings: () => void;
  onMessagesChange?: (messages: Message[]) => void;
}

export function ChatInterface({ onSettings, onMessagesChange }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>(() => StorageManager.getConversationObjects());
  const [activeConversationId, setActiveConversationId] = useState<string | null>(conversations.length ? conversations[conversations.length - 1].id : null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasMessages, setHasMessages] = useState(false);
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [activeTemplate, setActiveTemplate] = useState<{ template: LegalTemplate; fields: TemplateField[] } | null>(null);
  const [currentStage, setCurrentStage] = useState<{ stage: string; current: number; total: number } | null>(null);
  const [currentThinkingStages, setCurrentThinkingStages] = useState<ThinkingStage[]>([]);
  const [userName, setUserName] = useState<string | undefined>(() => StorageManager.getSettings().userName);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isCitationManagerOpen, setIsCitationManagerOpen] = useState(false);
  const { addToast } = useToast();

  // Update userName when settings change
  useEffect(() => {
    const settings = StorageManager.getSettings();
    setUserName(settings.userName);
  }, []);

  // Keyboard shortcut for search (Ctrl/Cmd+F)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
      if (e.key === 'Escape' && isSearchOpen) {
        setIsSearchOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen]);

  // Notify parent when messages change
  useEffect(() => {
    if (onMessagesChange) {
      onMessagesChange(messages);
    }
  }, [messages, onMessagesChange]);

  // Load messages from storage on mount (legacy chat state)
  useEffect(() => {
    const chatState = StorageManager.getChatState();
    if (chatState?.messages) {
      setMessages(chatState.messages);
      setHasMessages(chatState.messages.length > 0);
    }
  }, []);

  // If we have conversation objects and no messages loaded yet, load the active conversation
  useEffect(() => {
    if (messages.length === 0 && activeConversationId) {
      const conv = conversations.find(c => c.id === activeConversationId);
      if (conv) {
        setMessages(conv.messages);
        setHasMessages(conv.messages.length > 0);
      }
    }
  }, [activeConversationId, conversations]);

  // Handle import messages
  useEffect(() => {
    const handler = (event: any) => {
      const importedMessages = event.detail.messages;
      setMessages(prev => [...prev, ...importedMessages]);
      addToast({
        type: 'success',
        title: 'Imported',
        description: 'Previous conversation has been summarized and added as context',
        duration: 3000
      });
    };
    window.addEventListener('junas-import', handler);
    return () => window.removeEventListener('junas-import', handler);
  }, [addToast]);

  // Save messages to storage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      // Persist legacy chat state for backward compatibility
      StorageManager.saveChatState({
        messages,
        isLoading,
        currentProvider: 'gemini',
        apiKeys: StorageManager.getApiKeys(),
        settings: StorageManager.getSettings(),
      });
      setHasMessages(true);
      // Update active conversation object if exists
      if (activeConversationId) {
        const conv = conversations.find(c => c.id === activeConversationId);
        if (conv) {
          const updated: Conversation = { ...conv, messages, updatedAt: new Date() };
          StorageManager.saveConversationObject(updated);
          setConversations(prev => prev.map(c => c.id === updated.id ? updated : c));
        }
      }
    }
  }, [messages, isLoading, activeConversationId, conversations]);

  const handleSendMessage = useCallback(async (content: string) => {
    if (!content.trim()) return;

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

  setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    const startTime = Date.now(); // Track start time

    try {
      // Create assistant message for streaming
      const assistantMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };

  setMessages(prev => [...prev, assistantMessage]);

      // Get all messages including the new user message
  const allMessages = [...messages, userMessage];

      // Track reasoning metadata and thinking stages
      let reasoningMetadata: ReasoningMetadata | undefined;
      const thinkingStages: ThinkingStage[] = [];

      // Try streaming first, then fallback to non-streaming if provider doesn't support endpoint
      let fullResponse = '';
      try {
        const result = await ChatService.sendMessage(
          allMessages,
          (chunk: string) => {
            setMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMessage.id
                  ? { ...msg, content: msg.content + chunk }
                  : msg
              )
            );
          },
          {
            onStageChange: (stage, current, total) => {
              setCurrentStage({ stage, current, total });
            },
            onReasoningUpdate: (metadata) => {
              reasoningMetadata = metadata;
            },
            onThinkingStage: (stageUpdate) => {
              // Find existing stage of same type and update, or add new
              const existingIndex = thinkingStages.findIndex(s => s.stage === stageUpdate.stage);
              if (existingIndex >= 0) {
                thinkingStages[existingIndex] = stageUpdate;
              } else {
                thinkingStages.push(stageUpdate);
              }
              setCurrentThinkingStages([...thinkingStages]);
            },
          }
        );
        fullResponse = result.content;
        reasoningMetadata = result.reasoning;
      } catch (e: any) {
        // Fallback to non-streaming
        const result = await ChatService.sendMessage(allMessages);
        fullResponse = result.content;
        reasoningMetadata = result.reasoning;
      }

      // Clear stage indicators
      setCurrentStage(null);
      setCurrentThinkingStages([]);

      // Extract and lookup citations from the response
      const citations = await extractAndLookupCitations(fullResponse);

      // Calculate response time
      const responseTime = Date.now() - startTime;

      // Final update with complete response, citations, reasoning metadata, thinking stages, and response time
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                content: fullResponse,
                citations,
                reasoning: reasoningMetadata,
                thinkingStages: thinkingStages.length > 0 ? thinkingStages : undefined,
                responseTime
              }
            : msg
        )
      );

    } catch (error: any) {
      console.error('Error sending message:', error);
      
      // Show error toast
      addToast({
        type: 'error',
        title: 'Error',
        description: error.message || 'Failed to send message. Please check your API keys in settings.',
        duration: 5000,
      });
      
      // Add error message
      const errorMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.message}. Please check your API keys in settings.`,
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [messages]);


  const handleBranchFromMessage = useCallback((messageId: string) => {
    // Create a branch conversation up to messageId
    const branch = StorageManager.createBranchFrom(messages, messageId, { parentId: activeConversationId || undefined });
    setConversations(prev => [...prev, branch]);
    setActiveConversationId(branch.id);
    setMessages(branch.messages);
    addToast({
      type: 'info',
      title: 'Conversation Branched',
      description: 'A new conversation branch was created from this point.',
      duration: 3000,
    });
  }, [messages, activeConversationId, addToast]);

  const handleSelectConversation = useCallback((conversationId: string) => {
    const conv = conversations.find(c => c.id === conversationId);
    if (!conv) return;
    setActiveConversationId(conv.id);
    setMessages(conv.messages);
  }, [conversations]);

  const handleDeleteConversation = useCallback((conversationId: string) => {
    if (conversationId === activeConversationId) {
      setActiveConversationId(null);
      setMessages([]);
    }
    StorageManager.deleteConversation(conversationId);
    setConversations(prev => prev.filter(c => c.id !== conversationId));
    addToast({
      type: 'success',
      title: 'Deleted',
      description: 'Conversation removed',
      duration: 2000,
    });
  }, [activeConversationId, addToast]);

  const handleUpdateTags = useCallback((conversationId: string, tags: string[]) => {
    StorageManager.updateConversationTags(conversationId, tags);
    setConversations(prev => prev.map(c => c.id === conversationId ? { ...c, tags } : c));
    addToast({
      type: 'success',
      title: 'Tags Updated',
      description: 'Conversation tags saved.',
      duration: 2000,
    });
  }, [addToast]);

  const handlePromptSelect = useCallback((prompt: string) => {
    handleSendMessage(prompt);
  }, [handleSendMessage]);

  const handleCopyMessage = useCallback((content: string) => {
    navigator.clipboard.writeText(content);
    addToast({
      type: 'success',
      title: 'Copied',
      description: 'Message copied to clipboard',
      duration: 2000,
    });
  }, [addToast]);

  const handleRegenerateMessage = useCallback(async (messageId: string) => {
    const idx = messages.findIndex(m => m.id === messageId);
    if (idx === -1) return;
    const target = messages[idx];
    if (target.role !== 'assistant') return;

    try {
      setIsLoading(true);

      // Determine the context up to and including the prior user prompt
      let startIdx = idx;
      for (let i = idx; i >= 0; i--) {
        if (messages[i].role === 'user') { startIdx = i; break; }
      }
      const contextMessages = messages.slice(0, startIdx + 1);

  // Regeneration always uses standard depth per user request
  const nextDepth: ReasoningMetadata['reasoningDepth'] = 'standard';

  const result = await ChatService.sendMessage(contextMessages, undefined, { reasoningDepth: nextDepth });

      // Extract citations
      const citations = await extractAndLookupCitations(result.content);

      // Create alternative entry
      const altId = generateId();
      const alternative: NonNullable<Message['alternatives']>[number] = {
        id: altId,
        content: result.content,
        createdAt: new Date(),
        citations,
        reasoning: { ...result.reasoning, reasoningDepth: nextDepth },
      };

      // Update target message with new alternative and selection
      setMessages(prev => prev.map((m, i) => {
        if (i !== idx) return m;
        const alts = m.alternatives ? [...m.alternatives, alternative] : [alternative];
        return { ...m, alternatives: alts, selectedAltId: altId };
      }));

      addToast({
        type: 'success',
        title: 'Regenerated',
        description: 'Generated an alternative response.',
        duration: 2500,
      });
    } catch (e: any) {
      console.error('Regenerate failed', e);
      addToast({
        type: 'error',
        title: 'Regeneration failed',
        description: e.message || 'Could not regenerate response.',
      });
    } finally {
      setIsLoading(false);
    }
  }, [messages, addToast]);

  const handleEditUserMessage = useCallback(async (messageId: string, newContent: string) => {
    const idx = messages.findIndex(m => m.id === messageId);
    if (idx === -1) return;
    const target = messages[idx];
    if (target.role !== 'user') return;
    // Update content and trim subsequent messages
    const trimmed = messages.slice(0, idx + 1).map(m => m.id === messageId ? { ...m, content: newContent } : m);
    setMessages(trimmed);
    setIsLoading(true);
    try {
      // Send new assistant response based on edited context
      const userMessage = trimmed[idx];
      const assistantMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, assistantMessage]);

      const allMessages = [...trimmed];
      let reasoningMetadata: ReasoningMetadata | undefined;
      const thinkingStages: ThinkingStage[] = [];
      let fullResponse = '';
      try {
        const result = await ChatService.sendMessage(
          allMessages,
          (chunk: string) => {
            setMessages(prev => prev.map(msg => msg.id === assistantMessage.id ? { ...msg, content: msg.content + chunk } : msg));
          }
        );
        fullResponse = result.content;
        reasoningMetadata = result.reasoning;
      } catch (e: any) {
        const result = await ChatService.sendMessage(allMessages);
        fullResponse = result.content;
        reasoningMetadata = result.reasoning;
      }
      const citations = await extractAndLookupCitations(fullResponse);
      setMessages(prev => prev.map(msg => msg.id === assistantMessage.id ? { ...msg, content: fullResponse, citations, reasoning: reasoningMetadata, thinkingStages: thinkingStages.length ? thinkingStages : undefined } : msg));
      addToast({
        type: 'success',
        title: 'Message Edited',
        description: 'Conversation updated from edited point.',
        duration: 2500,
      });
    } catch (e: any) {
      addToast({
        type: 'error',
        title: 'Edit failed',
        description: e.message || 'Could not re-run after edit.',
      });
    } finally {
      setIsLoading(false);
    }
  }, [messages, addToast]);

  const handleSelectMessageVersion = useCallback((messageId: string, versionId: string | null) => {
    setMessages(prev => prev.map(m => m.id === messageId ? { ...m, selectedAltId: versionId || undefined } : m));
  }, []);

  const handleSelectTemplate = useCallback((template: LegalTemplate) => {
    // Extract fields from the template prompt
    const fields = extractTemplateFields(template.prompt);

    // Show the template form
    setActiveTemplate({ template, fields });
    setShowTemplateSelector(false);
  }, []);

  const handleTemplateFormSubmit = useCallback((formData: Record<string, string>) => {
    if (!activeTemplate) return;

    // Construct enriched prompt with user-provided data
    let enrichedPrompt = activeTemplate.template.prompt;

    // Add user context at the beginning
    const userContext = Object.entries(formData)
      .map(([key, value]) => {
        const field = activeTemplate.fields.find(f => f.id === key);
        return field ? `${field.label}: ${value}` : null;
      })
      .filter(Boolean)
      .join('\n');

    const finalPrompt = `Please draft the following legal document using the provided information and template guidelines.

USER PROVIDED INFORMATION:
${userContext}

TEMPLATE INSTRUCTIONS:
${activeTemplate.template.prompt}

Please generate a complete, professional legal document incorporating all the provided information. Ensure compliance with Singapore law and include all necessary clauses and provisions.`;

    // Close the form
    setActiveTemplate(null);

    // Send to AI
    handleSendMessage(finalPrompt);
  }, [activeTemplate, handleSendMessage]);

  const handleTemplateFormCancel = useCallback(() => {
    setActiveTemplate(null);
  }, []);

  const handleExportCitations = useCallback((format: 'endnote' | 'zotero' | 'bibtex') => {
    const allCitations = messages.flatMap(m => m.citations || []);
    if (allCitations.length === 0) {
      addToast({
        type: 'error',
        title: 'No Citations',
        description: 'No citations to export in this conversation.',
        duration: 2500,
      });
      return;
    }

    let content = '';
    if (format === 'bibtex') {
      content = exportToBibTeX(allCitations);
    } else if (format === 'endnote') {
      content = exportToEndNote(allCitations);
    } else {
      content = exportToZotero(allCitations);
    }

    downloadCitationFile(content, format);
    addToast({
      type: 'success',
      title: 'Exported',
      description: `Citations exported to ${format.toUpperCase()}.`,
      duration: 2500,
    });
  }, [messages, addToast]);

  return (
    <div className="flex flex-col h-full max-w-6xl mx-auto w-full">
      {/* Messages area */}
      <div className="flex-1 overflow-hidden">
        {/* Conversation switcher */}
        <div className="px-3 md:px-4 py-2 border-b bg-muted/30 flex items-center justify-between">
          <ConversationSwitcher
            conversations={conversations}
            activeId={activeConversationId}
            onSelect={handleSelectConversation}
            onDelete={handleDeleteConversation}
            onUpdateTags={handleUpdateTags}
            onNew={() => {
              const empty: Conversation = {
                id: crypto.randomUUID?.() || Math.random().toString(36).slice(2),
                title: 'New Conversation',
                messages: [],
                createdAt: new Date(),
                updatedAt: new Date(),
              };
              StorageManager.saveConversationObject(empty);
              setConversations(prev => [...prev, empty]);
              setActiveConversationId(empty.id);
              setMessages([]);
            }}
          />
          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={() => setIsCitationManagerOpen(true)}
            >
              Citations
            </Button>
          )}
        </div>
        {messages.length === 0 ? (
          <div className="pt-4 md:pt-6 px-4 md:px-0">
            <div className="text-center mb-6 md:mb-8">
              <h1 className="text-2xl sm:text-3xl md:text-4xl font-semibold text-foreground mb-2">
                {getGreeting()}{userName ? `, ${userName}` : ''}
              </h1>
              <p className="text-base md:text-lg text-muted-foreground">
                How can I assist you today?
              </p>
            </div>
            <HeroMarquee />
          </div>
        ) : (
          <div className="h-full flex flex-col">
            <div className="flex-1 overflow-hidden">
              <MessageList
                messages={messages}
                isLoading={isLoading}
                onCopyMessage={handleCopyMessage}
                onRegenerateMessage={handleRegenerateMessage}
                onSelectMessageVersion={handleSelectMessageVersion}
                onBranchFromMessage={handleBranchFromMessage}
                onEditUserMessage={handleEditUserMessage}
                currentThinkingStages={currentThinkingStages}
              />
            </div>
          </div>
        )}
      </div>

      {/* Reasoning progress indicator - above input */}
      {currentStage && isLoading && (
        <div className="px-3 md:px-4 py-2 border-t bg-muted/30">
          <ReasoningProgress
            currentStage={currentStage.current}
            totalStages={currentStage.total}
            stage={currentStage.stage}
          />
        </div>
      )}

      {/* Input area or Template Form */}
      {activeTemplate ? (
        <TemplateForm
          template={activeTemplate.template}
          fields={activeTemplate.fields}
          onSubmit={handleTemplateFormSubmit}
          onCancel={handleTemplateFormCancel}
        />
      ) : (
        <MessageInput
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          onOpenTemplates={() => setShowTemplateSelector(true)}
          onSelectTemplate={handleSelectTemplate}
        />
      )}

      {/* Template Selector */}
      <TemplateSelector
        isOpen={showTemplateSelector}
        onClose={() => setShowTemplateSelector(false)}
        onSelectTemplate={handleSelectTemplate}
      />

      {/* Legal Disclaimer Overlay */}
      <LegalDisclaimer />

      {/* Search Overlay */}
      <ChatSearch
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        messages={messages.map(m => ({ id: m.id, content: m.content, role: m.role }))}
      />

      {/* Citation Manager */}
      <CitationManager
        isOpen={isCitationManagerOpen}
        onClose={() => setIsCitationManagerOpen(false)}
        citations={messages.flatMap(m => m.citations || [])}
        onExport={handleExportCitations}
      />
    </div>
  );
}
