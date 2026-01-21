'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Message, Artifact } from '@/types/chat';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { ArtifactsTab } from './ArtifactsTab';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';
import { StorageManager } from '@/lib/storage';
import { ChatService } from '@/lib/ai/chat-service';
import { useToast } from '@/components/ui/toast';
import { generateId } from '@/lib/utils';
import { parseCommand, processLocalCommand, processAsyncLocalCommand } from '@/lib/commands/command-processor';
import { JUNAS_ASCII_LOGO } from '@/lib/constants';
import { getModelsWithStatus, generateText, AVAILABLE_MODELS } from '@/lib/ml/model-manager';
import { FileText, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatInterfaceProps {}

export function ChatInterface({}: ChatInterfaceProps = {}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [activeTab, setActiveTab] = useState<'chat' | 'artifacts'>('chat');
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
    
    // Check local model status
    const models = getModelsWithStatus();
    const downloadedCount = models.filter(m => m.isDownloaded).length;
    if (downloadedCount === AVAILABLE_MODELS.length) {
      setCurrentProvider('local');
    } else if (chatState?.currentProvider) {
      setCurrentProvider(chatState.currentProvider);
    }

    if (chatState?.messages) {
      setMessages(chatState.messages);
      setHasMessages(chatState.messages.length > 0);
    }
    if (chatState?.artifacts) {
      setArtifacts(chatState.artifacts);
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

    if (currentProvider === 'local') {
      try {
        const prompt = `Summarize conversation: ${conversationText}`;
        return await generateText(prompt);
      } catch (e) {
        console.error("Local summarization failed", e);
        return "Conversation imported.";
      }
    }

    const result = await ChatService.sendMessage(summarizationPrompt, undefined, currentProvider);
    return result.content;
  };

  // Save messages to storage whenever they change
  useEffect(() => {
    if (messages.length > 0 || artifacts.length > 0) {
      StorageManager.saveChatState({
        messages,
        artifacts,
        isLoading,
        currentProvider,
        apiKeys: StorageManager.getApiKeys(),
        settings: StorageManager.getSettings(),
      });
      setHasMessages(messages.length > 0);
    }
  }, [messages, artifacts, isLoading, currentProvider]);

  const handleSendMessage = useCallback(async (content: string) => {
    if (!content.trim()) return;

    // Check if this is a local command (legacy direct command)
    const parsedCommand = parseCommand(content);

    // For user message display, don't add context prefix to local commands
    let displayContent = content;
    let enrichedContent = content;

    // Add user context pre-prompt to the first message (only for AI commands)
    if (messages.length === 0 && (!parsedCommand || !parsedCommand.isLocal)) {
      const settings = StorageManager.getSettings();
      if (settings.userRole || settings.userPurpose) {
        const contextParts = [];
        if (settings.userRole) contextParts.push(`a ${settings.userRole}`);
        if (settings.userPurpose) contextParts.push(`using Junas for ${settings.userPurpose}`);
        const contextPrompt = `[Context: I am ${contextParts.join(' ')}]\n\n`;
        enrichedContent = contextPrompt + content;
      }
    }

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: parsedCommand?.isLocal ? displayContent : enrichedContent,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    const startTime = Date.now();

    // Create assistant message
    const assistantMessage: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, assistantMessage]);

    // Legacy Local Command Handling
    if (parsedCommand && parsedCommand.isLocal) {
      const result = processLocalCommand(parsedCommand);

      // Handle artifact generation
      if (result.success && result.artifact) {
        const newArtifact: Artifact = {
          id: generateId(),
          ...result.artifact,
          createdAt: Date.now(),
          messageId: assistantMessage.id
        };
        setArtifacts(prev => [newArtifact, ...prev]);
        addToast({
          title: "Artifact Generated",
          description: `Created ${newArtifact.title}`,
        });
        setActiveTab('artifacts'); // Switch to artifacts tab
      }

      if (!result.success && result.requiresModel) {
        const responseTime = Date.now() - startTime;
        setMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMessage.id
              ? { ...msg, content: result.content, responseTime }
              : msg
          )
        );
        setIsLoading(false);
        return;
      }

      if (result.content === '__ASYNC_MODEL_COMMAND__') {
        setMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMessage.id
              ? { ...msg, content: 'Loading model and processing...' }
              : msg
          )
        );

        try {
          const asyncResult = await processAsyncLocalCommand(parsedCommand);
          const responseTime = Date.now() - startTime;
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessage.id
                ? { ...msg, content: asyncResult.content, responseTime }
                : msg
            )
          );
        } catch (error: any) {
          const responseTime = Date.now() - startTime;
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessage.id
                ? { ...msg, content: `Error processing command: ${error.message}`, responseTime }
                : msg
            )
          );
        }
        setIsLoading(false);
        return;
      }

      const responseTime = Date.now() - startTime;
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? { ...msg, content: result.content, responseTime }
            : msg
        )
      );
      setIsLoading(false);
      return;
    }

    // AI Processing Loop (ReAct Pattern)
    // Supports both Local LLM and API Providers
    const processAIResponse = async (currentMessages: Message[], recursionDepth = 0) => {
      if (recursionDepth > 3) { // Limit tool loops
        return "Error: Maximum tool recursion depth reached.";
      }

      let aiResponseText = "";
      let rafId: number | null = null;
      let lastUpdate = 0;

      const updateMessageContent = (text: string) => {
        setMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMessage.id
              ? { ...msg, content: text }
              : msg
          )
        );
      };

      try {
        // 1. Get response from Provider (Local or API)
        if (currentProvider === 'local') {
          // Local Generation
          const prompt = currentMessages
            .slice(-6) // Slightly larger context
            .map(m => `${m.role === 'user' ? 'User' : m.role === 'system' ? 'System' : 'Assistant'}: ${m.content}`)
            .join('\n') + '\nAssistant:';
          
          aiResponseText = await generateText(prompt);
          updateMessageContent(aiResponseText);
        } else {
          // API Generation
          const result = await ChatService.sendMessage(
            currentMessages,
            (chunk: string) => {
              aiResponseText += chunk;
              const now = Date.now();
              if (!rafId && now - lastUpdate > 16) {
                lastUpdate = now;
                rafId = requestAnimationFrame(() => updateMessageContent(aiResponseText));
              }
            },
            currentProvider
          );
          
          if (rafId) cancelAnimationFrame(rafId);
          updateMessageContent(result.content);
          aiResponseText = result.content;
        }

        // 2. Check for Tool Commands (ReAct)
        // Expected format: COMMAND: <tool_id> <args>
        const commandMatch = aiResponseText.match(/^COMMAND:\s*([a-z-]+)\s*([\s\S]*)/i);
        
        if (commandMatch) {
          const commandId = commandMatch[1].toLowerCase() as any;
          const args = commandMatch[2].trim();
          const toolCommand = { command: commandId, args, isLocal: true }; // Treat as local execution context

          // Update UI to show we are executing a tool
          const toolStatusMsg = `[Executing tool: ${commandId}...]`;
          updateMessageContent(toolStatusMsg);

          let toolResultContent = "";

          // Execute Tool
          const syncResult = processLocalCommand(toolCommand);
          
          if (syncResult.success && syncResult.artifact) {
            const newArtifact: Artifact = {
              id: generateId(),
              ...syncResult.artifact,
              createdAt: Date.now(),
              messageId: assistantMessage.id
            };
            setArtifacts(prev => [newArtifact, ...prev]);
            addToast({
              title: "Artifact Generated",
              description: `Created ${newArtifact.title}`,
            });
            // We don't auto-switch tab here to avoid disrupting chat flow, but the toast helps
          }

          if (syncResult.content === '__ASYNC_MODEL_COMMAND__') {
             // Handle async tool
             const asyncResult = await processAsyncLocalCommand(toolCommand);
             toolResultContent = asyncResult.success ? asyncResult.content : `Tool Error: ${asyncResult.content}`;
          } else {
             // Handle sync tool
             toolResultContent = syncResult.success ? syncResult.content : `Tool Error: ${syncResult.content}`;
          }

          // 3. Feed result back to AI
          const updatedMessages = [
            ...currentMessages,
            { role: 'assistant', content: aiResponseText } as Message, // The command itself
            { role: 'system', content: `Tool Output for ${commandId}:\n${toolResultContent}\n\nBased on this output, provide the final answer to the user.` } as Message
          ];

          // Recursive call
          return await processAIResponse(updatedMessages, recursionDepth + 1);
        }

        // Final response (no tool command)
        return aiResponseText;

      } catch (error: any) {
        console.error("AI Processing Error:", error);
        throw error;
      }
    };

    try {
      const allMessages = [...messages, userMessage];
      const finalResponse = await processAIResponse(allMessages);
      
      const responseTime = Date.now() - startTime;
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? { ...msg, content: finalResponse, responseTime }
            : msg
        )
      );
    } catch (error: any) {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? { ...msg, content: `Error: ${error.message}` }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }

  }, [messages]);


  const handlePromptSelect = useCallback((prompt: string) => {
    handleSendMessage(prompt);
  }, [handleSendMessage]);

  const copyTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleCopyMessage = useCallback(async (content: string) => {
    // Prevent multiple rapid copy toasts
    if (copyTimeoutRef.current) {
      return;
    }

    const copyToClipboard = async (text: string): Promise<boolean> => {
      // Try modern clipboard API first
      try {
        if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
          return true;
        }
      } catch {
        // Fall through to fallback
      }

      // Fallback for older browsers or non-HTTPS contexts
      try {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        const success = document.execCommand('copy');
        document.body.removeChild(textArea);
        return success;
      } catch {
        return false;
      }
    };

    const success = await copyToClipboard(content);

    if (success) {
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
    } else {
      addToast({
        type: 'error',
        title: 'Copy failed',
        description: 'Unable to copy to clipboard',
        duration: 2000,
      });
    }
  }, [addToast]);

  const handleRegenerateMessage = useCallback((messageId: string) => {
    // TODO: Implement message regeneration
    console.log('Regenerate message:', messageId);
  }, []);



  return (
    <div className="flex flex-col h-full w-full">
      {/* Tab Header */}
      <div className="flex items-center border-b px-4 h-10 shrink-0 gap-4">
        <button 
            onClick={() => setActiveTab('chat')}
            className={cn(
                "flex items-center gap-2 h-full text-xs font-mono border-b-2 transition-colors px-2",
                activeTab === 'chat' 
                    ? "border-primary text-foreground" 
                    : "border-transparent text-muted-foreground hover:text-foreground"
            )}
        >
            <MessageSquare className="h-3 w-3" />
            CHAT
        </button>
        <button 
            onClick={() => setActiveTab('artifacts')}
            className={cn(
                "flex items-center gap-2 h-full text-xs font-mono border-b-2 transition-colors px-2",
                activeTab === 'artifacts' 
                    ? "border-primary text-foreground" 
                    : "border-transparent text-muted-foreground hover:text-foreground"
            )}
        >
            <FileText className="h-3 w-3" />
            ARTIFACTS {artifacts.length > 0 && `(${artifacts.length})`}
        </button>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-hidden relative">
        <div className={cn("absolute inset-0 flex flex-col transition-opacity duration-200", activeTab === 'chat' ? "opacity-100 z-10" : "opacity-0 z-0 pointer-events-none")}>
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full px-4 py-8">
            <div className="text-center max-w-2xl w-full">
              <div className="overflow-x-auto my-8">
                <pre className="text-muted-foreground text-xs md:text-sm font-mono leading-tight inline-block">
                  {JUNAS_ASCII_LOGO}
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
        
        <div className={cn("absolute inset-0 bg-background transition-opacity duration-200", activeTab === 'artifacts' ? "opacity-100 z-10" : "opacity-0 z-0 pointer-events-none")}>
            <ArtifactsTab artifacts={artifacts} />
        </div>
      </div>

      {/* Input area - Only show when in chat tab or leave always visible? 
          Usually input is relevant for chat. 
          If in artifacts tab, maybe hide input or disable it? 
          Let's keep it visible but maybe disabled if in artifacts, or just let user type command.
      */}
      <div className={cn("transition-all duration-200", activeTab === 'artifacts' ? "opacity-50 pointer-events-none" : "opacity-100")}>
        <MessageInput
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            currentProvider={currentProvider}
            onProviderChange={setCurrentProvider}
        />
      </div>

      {/* Legal Disclaimer Overlay */}
      <LegalDisclaimer />
    </div>
  );
}
