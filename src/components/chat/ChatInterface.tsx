'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Message } from '@/types/chat';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';
import { StorageManager } from '@/lib/storage';
import { ChatService } from '@/lib/ai/chat-service';
import { useToast } from '@/components/ui/toast';
import { generateId } from '@/lib/utils';
import { AttachedFile } from './ContextAttachment';

interface ChatInterfaceProps {}

export function ChatInterface({}: ChatInterfaceProps = {}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasMessages, setHasMessages] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<string>('gemini');
  const [hasProfileConfig, setHasProfileConfig] = useState(false);
  const { addToast } = useToast();

  // Check if user has configured their profile
  useEffect(() => {
    const settings = StorageManager.getSettings();
    setHasProfileConfig(!!(settings.userRole || settings.userPurpose));
  }, [messages]);

  // Load messages from storage on mount
  useEffect(() => {
    const chatState = StorageManager.getChatState();
    if (chatState?.messages) {
      setMessages(chatState.messages);
      setHasMessages(chatState.messages.length > 0);
    }
    if (chatState?.currentProvider) {
      setCurrentProvider(chatState.currentProvider);
    }
  }, []);

  // Handle import messages
  useEffect(() => {
    const handler = async (event: any) => {
      const importedMessages = event.detail.messages;
      
      // Show loading message
      const loadingMessage: Message = {
        id: 'import-loading',
        role: 'system',
        content: 'loading',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, loadingMessage]);
      setIsLoading(true);
      
      try {
        // Summarize the conversation
        const summary = await summarizeImportedConversation(importedMessages);
        
        // Remove loading message and add the summary response
        setMessages(prev => {
          const filtered = prev.filter(m => m.id !== 'import-loading');
          return [
            ...filtered,
            {
              id: generateId(),
              role: 'assistant',
              content: summary,
              timestamp: new Date(),
            }
          ];
        });
        
        addToast({
          type: 'success',
          title: 'Imported',
          description: 'Previous conversation has been summarized',
          duration: 3000
        });
      } catch (error) {
        // Remove loading message on error
        setMessages(prev => prev.filter(m => m.id !== 'import-loading'));
        addToast({
          type: 'error',
          title: 'Import Failed',
          description: 'Failed to summarize conversation',
          duration: 3000
        });
      } finally {
        setIsLoading(false);
      }
    };
    window.addEventListener('junas-import', handler);
    return () => window.removeEventListener('junas-import', handler);
  }, [addToast]);

  const summarizeImportedConversation = async (messages: Message[]): Promise<string> => {
    const conversationText = messages
      .map(msg => `${msg.role.toUpperCase()}: ${msg.content}`)
      .join('\n\n');

    const summarizationPrompt: Message[] = [
      {
        id: 'user-prompt',
        role: 'user',
        content: `Provide a single sentence (maximum 20 words) summarizing what the following conversation was about:

${conversationText}

Reply ONLY with: "You were previously talking about [summary]. Feel free to continue asking about it."`,
        timestamp: new Date(),
      },
    ];

    const result = await ChatService.sendMessage(summarizationPrompt, undefined, currentProvider);
    return result.content;
  };

  // Save messages to storage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      StorageManager.saveChatState({
        messages,
        isLoading,
        currentProvider,
        apiKeys: StorageManager.getApiKeys(),
        settings: StorageManager.getSettings(),
      });
      setHasMessages(true);
    }
  }, [messages, isLoading, currentProvider]);

  const handleSendMessage = useCallback(async (content: string, attachedFiles?: AttachedFile[]) => {
    if (!content.trim()) return;

    // Process attached files and add context to the message
    let enrichedContent = content;

    // Add user context pre-prompt to the first message
    if (messages.length === 0) {
      const settings = StorageManager.getSettings();
      if (settings.userRole || settings.userPurpose) {
        const contextParts = [];
        if (settings.userRole) contextParts.push(`a ${settings.userRole}`);
        if (settings.userPurpose) contextParts.push(`using Junas for ${settings.userPurpose}`);
        const contextPrompt = `[Context: I am ${contextParts.join(' ')}]\n\n`;
        enrichedContent = contextPrompt + content;
      }
    }

    if (attachedFiles && attachedFiles.length > 0) {
      const filesContext = attachedFiles.map(file => {
        return `\n\n[Attached File: ${file.name}]\n${
          file.type.startsWith('image/')
            ? '[Image file - content embedded]'
            : file.content.slice(0, 5000) // Limit to first 5000 chars
        }\n[End of ${file.name}]`;
      }).join('\n');

      enrichedContent = `${enrichedContent}\n\n--- Context from attached files ---${filesContext}`;
    }

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: enrichedContent,
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

      // Batching variables for smooth streaming
      let accumulatedContent = '';
      let rafId: number | null = null;
      let lastUpdate = 0;

      const updateMessage = () => {
        setMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMessage.id
              ? { ...msg, content: accumulatedContent }
              : msg
          )
        );
        rafId = null;
      };

      // Try streaming first, then fallback to non-streaming if provider doesn't support endpoint
      let fullResponse = '';
      try {
        const result = await ChatService.sendMessage(
          allMessages,
          (chunk: string) => {
            accumulatedContent += chunk;

            // Batch updates using requestAnimationFrame for smooth rendering
            // Only update at most every 16ms (60fps) to reduce jitter
            const now = Date.now();
            if (!rafId && now - lastUpdate > 16) {
              lastUpdate = now;
              rafId = requestAnimationFrame(updateMessage);
            }
          },
          currentProvider
        );

        // Ensure final update is applied
        if (rafId) {
          cancelAnimationFrame(rafId);
        }
        updateMessage();

        fullResponse = result.content;
      } catch (e: any) {
        // Fallback to non-streaming
        const result = await ChatService.sendMessage(allMessages, undefined, currentProvider);
        fullResponse = result.content;
      }

      // Calculate response time
      const responseTime = Date.now() - startTime;

      // Final update with complete response and response time
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                content: fullResponse,
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

  const copyTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleCopyMessage = useCallback((content: string) => {
    // Prevent multiple rapid copy toasts
    if (copyTimeoutRef.current) {
      return;
    }

    navigator.clipboard.writeText(content);
    addToast({
      type: 'success',
      title: 'Copied',
      description: 'Message copied to clipboard',
      duration: 2000,
    });

    // Set a timeout to prevent multiple toasts within 2 seconds
    copyTimeoutRef.current = setTimeout(() => {
      copyTimeoutRef.current = null;
    }, 2000);
  }, [addToast]);

  const handleRegenerateMessage = useCallback((messageId: string) => {
    // TODO: Implement message regeneration
    console.log('Regenerate message:', messageId);
  }, []);



  return (
    <div className="flex flex-col h-full w-full">
      {/* Messages area */}
      <div className="flex-1 overflow-hidden">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full px-4 py-8">
            <div className="text-center max-w-2xl w-full">
              <div className="mt-6 text-xs md:text-sm text-muted-foreground font-mono leading-relaxed space-y-2">
                <p>
                  Your AI-powered legal assistant for Singapore law.
                </p>
                <p>
                  Junas helps you research case law, analyze contracts, draft legal documents,
                  and navigate Singapore's legal framework with ease.
                </p>
                <p className="text-xs opacity-75">
                  [ Bring your own API keys • Privacy-focused • All data stays in your browser ]
                </p>
              </div>
              <div className="overflow-x-auto my-8">
                <pre className="text-muted-foreground text-xs md:text-sm font-mono leading-tight inline-block">
{`     ██╗██╗   ██╗███╗   ██╗ █████╗ ███████╗
     ██║██║   ██║████╗  ██║██╔══██╗██╔════╝
     ██║██║   ██║██╔██╗ ██║███████║███████╗
██   ██║██║   ██║██║╚██╗██║██╔══██║╚════██║
╚█████╔╝╚██████╔╝██║ ╚████║██║  ██║███████║
 ╚════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝`}
                </pre>
              </div>
              <p className="text-xs text-muted-foreground font-mono mt-6">v0.1.0</p>
            </div>
          </div>
        ) : (
          <div className="h-full flex flex-col">
            <div className="flex-1 overflow-hidden">
              <MessageList
                messages={messages}
                isLoading={isLoading}
                onCopyMessage={handleCopyMessage}
                onRegenerateMessage={handleRegenerateMessage}
              />
            </div>
          </div>
        )}
      </div>

      {/* Input area */}
      <MessageInput
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        currentProvider={currentProvider}
        onProviderChange={setCurrentProvider}
      />

      {/* Legal Disclaimer Overlay */}
      <LegalDisclaimer />
    </div>
  );
}
