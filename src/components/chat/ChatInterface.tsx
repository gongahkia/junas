'use client';

import { useState, useEffect, useCallback } from 'react';
import { Message } from '@/types/chat';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { HeroMarquee } from './HeroMarquee';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';
import { StorageManager } from '@/lib/storage';
import { ChatService } from '@/lib/ai/chat-service';
import { useToast } from '@/components/ui/toast';
import { generateId } from '@/lib/utils';
import { AttachedFile } from './ContextAttachment';

function getGreeting(): string {
  const hour = new Date().getHours();
  const greetings = [
    "Good morning",
    "Good afternoon", 
    "Good evening",
    "What's up",
    "What's shaking",
    "Hey there",
    "Hi there",
    "Hello",
    "Howdy",
    "Greetings",
    "Welcome back",
    "Salutations",
    "Ahoy",
    "Yo",
    "How's it going",
    "Long time no see",
    "Glad you're back",
    "Great to see you",
    "Pleasure to have you back",
    "It's been a minute",
  ];
  
  // Time-based greetings during appropriate hours
  if (hour < 12) {
    return Math.random() < 0.7 ? 'Good morning' : greetings[Math.floor(Math.random() * 3) + 3];
  }
  if (hour < 18) {
    return Math.random() < 0.7 ? 'Good afternoon' : greetings[Math.floor(Math.random() * 3) + 3];
  }
  return Math.random() < 0.7 ? 'Good evening' : greetings[Math.floor(Math.random() * 3) + 3];
}

interface ChatInterfaceProps {
  onMessagesChange?: (messages: Message[]) => void;
  scrollToMessageId?: string;
}

export function ChatInterface({ onMessagesChange, scrollToMessageId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasMessages, setHasMessages] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<string>('gemini');
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
    
    if (attachedFiles && attachedFiles.length > 0) {
      const filesContext = attachedFiles.map(file => {
        return `\n\n[Attached File: ${file.name}]\n${
          file.type.startsWith('image/') 
            ? '[Image file - content embedded]' 
            : file.content.slice(0, 5000) // Limit to first 5000 chars
        }\n[End of ${file.name}]`;
      }).join('\n');
      
      enrichedContent = `${content}\n\n--- Context from attached files ---${filesContext}`;
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



  return (
    <div className="flex flex-col h-full max-w-6xl mx-auto w-full">
      {/* Messages area */}
      <div className="flex-1 overflow-hidden">
        {messages.length === 0 ? (
          <div className="pt-4 md:pt-6 px-4 md:px-0">
            <div className="text-center mb-6 md:mb-8">
              <h1 className="text-2xl sm:text-3xl md:text-4xl font-semibold text-foreground mb-2">
                {userName ? `${getGreeting()}, ${userName}` : getGreeting()}
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
                scrollToMessageId={scrollToMessageId}
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
