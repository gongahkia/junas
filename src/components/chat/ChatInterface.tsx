'use client';

import { useState, useEffect, useCallback } from 'react';
import { Message } from '@/types/chat';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { HeroMarquee } from './HeroMarquee';
import { StorageManager } from '@/lib/storage';
import { ChatService } from '@/lib/ai/chat-service';
import { useToast } from '@/components/ui/toast';
import { generateId } from '@/lib/utils';

interface ChatInterfaceProps {
  onSettings: () => void;
  onMessagesChange?: (messages: Message[]) => void;
}

export function ChatInterface({ onSettings, onMessagesChange }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasMessages, setHasMessages] = useState(false);
  const { addToast } = useToast();

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
        fullResponse = await ChatService.sendMessage(
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
      } catch (e: any) {
        // Fallback to non-streaming
        fullResponse = await ChatService.sendMessage(allMessages);
      }

      // Final update with complete response
      setMessages(prev => 
        prev.map(msg => 
          msg.id === assistantMessage.id 
            ? { ...msg, content: fullResponse }
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
          <div className="pt-6">
            <HeroMarquee />
          </div>
        ) : (
          <MessageList
            messages={messages}
            isLoading={isLoading}
            onCopyMessage={handleCopyMessage}
            onRegenerateMessage={handleRegenerateMessage}
          />
        )}
      </div>

      {/* Input area */}
      <MessageInput
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
      />
    </div>
  );
}
