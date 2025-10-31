'use client';

import { useState, useEffect, useCallback } from 'react';
import { Message, ReasoningMetadata, ThinkingStage } from '@/types/chat';
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
import { useToast } from '@/components/ui/toast';
import { generateId } from '@/lib/utils';
import { extractTemplateFields, type LegalTemplate, type TemplateField } from '@/lib/templates';

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
  const [isLoading, setIsLoading] = useState(false);
  const [hasMessages, setHasMessages] = useState(false);
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [activeTemplate, setActiveTemplate] = useState<{ template: LegalTemplate; fields: TemplateField[] } | null>(null);
  const [currentStage, setCurrentStage] = useState<{ stage: string; current: number; total: number } | null>(null);
  const [currentThinkingStages, setCurrentThinkingStages] = useState<ThinkingStage[]>([]);
  const [userName, setUserName] = useState<string | undefined>(() => StorageManager.getSettings().userName);
  const { addToast } = useToast();

  // Update userName when settings change
  useEffect(() => {
    const settings = StorageManager.getSettings();
    setUserName(settings.userName);
  }, []);

  // Notify parent when messages change
  useEffect(() => {
    if (onMessagesChange) {
      onMessagesChange(messages);
    }
  }, [messages, onMessagesChange]);

  // Load messages from storage on mount
  useEffect(() => {
    const chatState = StorageManager.getChatState();
    if (chatState?.messages) {
      setMessages(chatState.messages);
      setHasMessages(chatState.messages.length > 0);
    }
  }, []);

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
      StorageManager.saveChatState({
        messages,
        isLoading,
        currentProvider: 'gemini',
        apiKeys: StorageManager.getApiKeys(),
        settings: StorageManager.getSettings(),
      });
      setHasMessages(true);
    }
  }, [messages, isLoading]);

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

  const handleRegenerateMessage = useCallback((messageId: string) => {
    // TODO: Implement message regeneration
    console.log('Regenerate message:', messageId);
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

  return (
    <div className="flex flex-col h-full max-w-6xl mx-auto w-full">
      {/* Messages area */}
      <div className="flex-1 overflow-hidden">
        {messages.length === 0 ? (
          <div className="pt-6">
            <div className="text-center mb-8">
              <h1 className="text-4xl font-semibold text-foreground mb-2">
                {getGreeting()}{userName ? `, ${userName}` : ''}
              </h1>
              <p className="text-lg text-muted-foreground">
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
                currentThinkingStages={currentThinkingStages}
              />
            </div>
          </div>
        )}
      </div>

      {/* Reasoning progress indicator - above input */}
      {currentStage && isLoading && (
        <div className="px-4 py-2 border-t bg-muted/30">
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
    </div>
  );
}
