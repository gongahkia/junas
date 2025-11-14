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

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

interface ChatInterfaceProps {
  onSettings: () => void;
  onMessagesChange?: (messages: Message[]) => void;
  scrollToMessageId?: string;
}

export function ChatInterface({ onSettings, onMessagesChange, scrollToMessageId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasMessages, setHasMessages] = useState(false);
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
          }
        );
        fullResponse = result.content;
      } catch (e: any) {
        // Fallback to non-streaming
        const result = await ChatService.sendMessage(allMessages);
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
      />

      {/* Legal Disclaimer Overlay */}
      <LegalDisclaimer />
    </div>
  );
}
