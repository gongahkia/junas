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
import { FileText, MessageSquare, GitGraph } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ConfirmationDialog } from './ConfirmationDialog';
import { TreeView } from './TreeView';
import { estimateTokens, estimateCost } from '@/lib/ai/token-utils';
import { createTreeFromLinear, addChild, getLinearHistory, getBranchSiblings } from '@/lib/chat-tree';
import { useJunasContext } from '@/lib/context/JunasContext';

interface ChatInterfaceProps {
  activeTab?: 'chat' | 'artifacts' | 'tree';
  onTabChange?: (tab: 'chat' | 'artifacts' | 'tree') => void;
}

export function ChatInterface({ activeTab: propActiveTab, onTabChange }: ChatInterfaceProps = {}) {
  // Use centralized state from context
  const {
    settings,
    chatState,
    conversations,
    updateChatState,
    saveConversation,
    configuredProviders
  } = useJunasContext();

  const [messages, setMessages] = useState<Message[]>([]);
  const [nodeMap, setNodeMap] = useState<Record<string, Message>>({});
  const [currentLeafId, setCurrentLeafId] = useState<string | undefined>(undefined);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [conversationId, setConversationId] = useState<string>(generateId());
  const [conversationTitle, setConversationTitle] = useState<string>('');

  const [localActiveTab, setLocalActiveTab] = useState<'chat' | 'artifacts' | 'tree'>('chat');
  const activeTab = propActiveTab ?? localActiveTab;
  const setActiveTab = onTabChange ?? setLocalActiveTab;

  const [isLoading, setIsLoading] = useState(false);
  const [hasMessages, setHasMessages] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<string>('gemini');
  const [hasProfileConfig, setHasProfileConfig] = useState(false);
  const { addToast } = useToast();

  const totalTokens = messages.reduce((acc, msg) => acc + (msg.tokenCount || 0), 0);
  const totalCost = messages.reduce((acc, msg) => acc + (msg.cost || 0), 0);

  const [confirmation, setConfirmation] = useState({
    isOpen: false,
    title: '',
    description: '',
    resolve: undefined as ((value: boolean) => void) | undefined,
  });

  const requestConfirmation = (title: string, description: string): Promise<boolean> => {
    return new Promise((resolve) => {
      setConfirmation({
        isOpen: true,
        title,
        description,
        resolve,
      });
    });
  };

  const handleConfirmationResult = (result: boolean) => {
    if (confirmation.resolve) {
      confirmation.resolve(result);
    }
    setConfirmation(prev => ({ ...prev, isOpen: false }));
  };

  // Check if user has configured their profile
  useEffect(() => {
    setHasProfileConfig(!!(settings.userRole || settings.userPurpose));
  }, [messages, settings]);

  // Sync with context chat state on load
  useEffect(() => {
    if (!chatState) return;

    // Check local model status (this logic stays local until we move ML manager to context too)
    const models = getModelsWithStatus();
    const downloadedCount = models.filter(m => m.isDownloaded).length;
    if (downloadedCount === AVAILABLE_MODELS.length) {
      setCurrentProvider('local');
    } else if (chatState.currentProvider) {
      setCurrentProvider(chatState.currentProvider);
    }

    if (chatState.messages) {
      if (chatState.nodeMap && chatState.currentLeafId) {
        setNodeMap(chatState.nodeMap);
        setCurrentLeafId(chatState.currentLeafId);
        setMessages(getLinearHistory(chatState.nodeMap, chatState.currentLeafId));
      } else {
        // Migration from linear to tree
        const { nodeMap: newMap, leafId } = createTreeFromLinear(chatState.messages);
        setNodeMap(newMap);
        setCurrentLeafId(leafId);
        setMessages(chatState.messages);
      }
      setHasMessages(chatState.messages.length > 0);
    }
    if (chatState.artifacts) {
      setArtifacts(chatState.artifacts);
    }

    // Find matching conversation in history to set ID/Title
    const matchingConv = conversations.find(c =>
      c.messages.length === chatState.messages?.length &&
      c.messages[0]?.id === chatState.messages?.[0]?.id
    );

    if (matchingConv) {
      setConversationId(matchingConv.id);
      setConversationTitle(matchingConv.title);
    }
  }, [chatState]); // Only re-run if context chatState changes externally (e.g. history selection)

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
        content: `Provide a single sentence (maximum 20 words) summarizing what the following conversation was about:\n\n${conversationText}\n\nReply ONLY with: "You were previously talking about [summary]. Feel free to continue asking about it."`,
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

    const result = await ChatService.sendMessage(summarizationPrompt, configuredProviders, settings, undefined, currentProvider);
    return result.content;
  };

  // ... (useEffect for saving stays same)

  // Generate a title for the conversation after first exchange
  useEffect(() => {
    if (messages.length >= 2 && !conversationTitle && !isLoading) {
      const generateTitle = async () => {
        try {
          const titlePrompt = [
            { role: 'user', content: `Summarize this conversation start into a 3-5 word title. Reply ONLY with the title text.\n\nUser: ${messages[0].content}\nAssistant: ${messages[1].content}` } as Message
          ];

          let title = '';
          if (currentProvider === 'local') {
            title = await generateText(`Title for: ${messages[0].content}`);
          } else {
            const result = await ChatService.sendMessage(titlePrompt, configuredProviders, settings, undefined, currentProvider);
            title = result.content.replace(/^["']|["']$/g, '').trim();
          }

          if (title) {
            setConversationTitle(title);
          }
        } catch (e) {
          console.error("Failed to generate title", e);
        }
      };
      generateTitle();
    }
  }, [messages, conversationTitle, isLoading, currentProvider]);

  // AI Processing Loop (ReAct Pattern)
  const generateResponse = useCallback(async (
    currentMessages: Message[],
    assistantMessageId: string,
    recursionDepth = 0
  ) => {
    const settings = StorageManager.getSettings();
    const maxDepth = settings.agentMode ? 10 : 3;

    if (recursionDepth > maxDepth) {
      return "Error: Maximum tool recursion depth reached.";
    }

    let aiResponseText = "";
    let rafId: number | null = null;
    let lastUpdate = 0;

    const updateMessageContent = (text: string) => {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, content: text }
            : msg
        )
      );
      setNodeMap(prev => ({
        ...prev,
        [assistantMessageId]: { ...prev[assistantMessageId], content: text }
      }));
    };

    try {
      // 1. Get response from Provider (Local or API)
      if (currentProvider === 'local') {
        let prompt = "";
        if (settings.agentMode) {
          prompt = "System: You are Junas, a Singapore legal AI. You can use tools by replying ONLY with COMMAND: tool-id args. Available tools: web-search (for online info), fetch-url (for websites), extract-entities (for legal names), summarize-local (for summaries). If you need to search the web, use COMMAND: web-search query.\n\n";
        }

        prompt += currentMessages
          .slice(-6)
          .map(m => `${m.role === 'user' ? 'User' : m.role === 'system' ? 'System' : 'Assistant'}: ${m.content}`)
          .join('\n') + '\nAssistant:';

        aiResponseText = await generateText(prompt);
        updateMessageContent(aiResponseText);
      } else {
        const result = await ChatService.sendMessage(
          currentMessages,
          configuredProviders,
          settings,
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

      // 2. Check for Tool Commands
      const commandMatch = aiResponseText.match(/^COMMAND:\s*([a-z-]+)\s*([\s\S]*)/i);

      if (commandMatch) {
        const commandId = commandMatch[1].toLowerCase() as any;
        const args = commandMatch[2].trim();

        // Check for destructive commands requiring confirmation
        if (['generate-document', 'write-file', 'delete-file'].includes(commandId)) {
          const approved = await requestConfirmation(
            "Execute Tool?",
            `The AI wants to run '${commandId}'. This action might modify or create files.`
          );

          if (!approved) {
            const updatedMessages = [
              ...currentMessages,
              { role: 'assistant', content: aiResponseText } as Message,
              { role: 'system', content: `Tool Execution Denied: User cancelled execution of ${commandId}.` } as Message
            ];
            return await generateResponse(updatedMessages, assistantMessageId, recursionDepth + 1);
          }
        }

        const toolCommand = { command: commandId, args, isLocal: true };

        updateMessageContent(`[Executing tool: ${commandId}...]`);

        let toolResultContent = "";
        const syncResult = processLocalCommand(toolCommand);

        if (syncResult.success && syncResult.artifact) {
          const newArtifact: Artifact = {
            id: generateId(),
            ...syncResult.artifact,
            createdAt: Date.now(),
            messageId: assistantMessageId
          };
          setArtifacts(prev => [newArtifact, ...prev]);
          addToast({
            title: "Artifact Generated",
            description: `Created ${newArtifact.title}`,
          });
        }

        if (syncResult.content === '__ASYNC_MODEL_COMMAND__') {
          const asyncResult = await processAsyncLocalCommand(toolCommand);
          toolResultContent = asyncResult.success ? asyncResult.content : `Tool Error: ${asyncResult.content}`;
        } else {
          toolResultContent = syncResult.success ? syncResult.content : `Tool Error: ${syncResult.content}`;
        }

        // 3. Feed result back to AI
        const updatedMessages = [
          ...currentMessages,
          { role: 'assistant', content: aiResponseText } as Message,
          { role: 'system', content: `Tool Output for ${commandId}:\n${toolResultContent}\n\nBased on this output, provide the final answer to the user.` } as Message
        ];

        return await generateResponse(updatedMessages, assistantMessageId, recursionDepth + 1);
      }

      return aiResponseText;

    } catch (error: unknown) {
      console.error("AI Processing Error:", error);
      throw error;
    }
  }, [currentProvider, addToast]);

  const handleSendMessage = useCallback(async (content: string) => {
    if (!content.trim()) return;

    // Resolve chained commands (e.g. /summarize (/fetch-url ...))
    // We do this before determining if it is a command or simple message
    // Note: importing resolveCommandString dynamically to ensure no circular deps if any, 
    // although it is imported at top level in my plan, but let's be safe or just use the one from imports if I added it.
    // I need to add import to the top of file too.
    const { resolveCommandString } = await import('@/lib/commands/command-processor');
    const resolvedContent = await resolveCommandString(content);

    // Check if this is a local command (legacy direct command)
    const parsedCommand = parseCommand(resolvedContent);

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
      tokenCount: estimateTokens(parsedCommand?.isLocal ? displayContent : enrichedContent),
      cost: estimateCost(estimateTokens(parsedCommand?.isLocal ? displayContent : enrichedContent), currentProvider, '', 'input'),
      parentId: currentLeafId,
    };

    // Update tree
    const afterUserMap = addChild(nodeMap, currentLeafId || '', userMessage);
    setNodeMap(afterUserMap);
    setCurrentLeafId(userMessage.id);
    setMessages(prev => [...prev, userMessage]);

    setIsLoading(true);

    const startTime = Date.now();

    // Create assistant message
    const assistantMessage: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      parentId: userMessage.id,
    };

    // Update tree with assistant
    const afterAssistantMap = addChild(afterUserMap, userMessage.id, assistantMessage);
    setNodeMap(afterAssistantMap);
    setCurrentLeafId(assistantMessage.id);
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
        } catch (error: unknown) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          const responseTime = Date.now() - startTime;
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessage.id
                ? { ...msg, content: `Error processing command: ${errorMessage}`, responseTime }
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

    try {
      const allMessages = [...messages, userMessage];
      const finalResponse = await generateResponse(allMessages, assistantMessage.id);

      const responseTime = Date.now() - startTime;
      const tokens = estimateTokens(finalResponse);
      const cost = estimateCost(tokens, currentProvider, '', 'output');

      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? { ...msg, content: finalResponse, responseTime, tokenCount: tokens, cost }
            : msg
        )
      );
      setNodeMap(prev => ({
        ...prev,
        [assistantMessage.id]: {
          ...prev[assistantMessage.id],
          content: finalResponse,
          responseTime,
          tokenCount: tokens,
          cost
        }
      }));
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? { ...msg, content: `Error: ${errorMessage}` }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }

  }, [messages, generateResponse, addToast, setActiveTab]);

  const handleRegenerateMessage = useCallback(async (messageId: string) => {
    const messageIndex = messages.findIndex(m => m.id === messageId);
    if (messageIndex === -1) return;
    const msgToRegenerate = messages[messageIndex];

    // We can only regenerate assistant messages
    if (msgToRegenerate.role !== 'assistant') return;

    // Get context up to this message (excluding the message itself)
    const contextMessages = messages.slice(0, messageIndex);
    const parentId = msgToRegenerate.parentId;

    // Reset state to this point
    setIsLoading(true);

    // Create new assistant message placeholder (sibling)
    const newAssistantMessage: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      parentId: parentId,
    };

    // Update tree: Add new sibling and switch branch
    const afterRegenMap = addChild(nodeMap, parentId || '', newAssistantMessage);
    setNodeMap(afterRegenMap);
    setCurrentLeafId(newAssistantMessage.id);

    // Update messages: Keep context + new placeholder
    setMessages([...contextMessages, newAssistantMessage]);

    const startTime = Date.now();

    try {
      const finalResponse = await generateResponse(contextMessages, newAssistantMessage.id);

      const responseTime = Date.now() - startTime;
      const tokens = estimateTokens(finalResponse);
      const cost = estimateCost(tokens, currentProvider, '', 'output');

      setMessages(prev =>
        prev.map(msg =>
          msg.id === newAssistantMessage.id
            ? { ...msg, content: finalResponse, responseTime, tokenCount: tokens, cost }
            : msg
        )
      );
      setNodeMap(prev => ({
        ...prev,
        [newAssistantMessage.id]: {
          ...prev[newAssistantMessage.id],
          content: finalResponse,
          responseTime,
          tokenCount: tokens,
          cost
        }
      }));
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === newAssistantMessage.id
            ? { ...msg, content: `Error: ${errorMessage}` }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [messages, generateResponse, nodeMap, currentProvider]);

  const handleEditMessage = useCallback(async (messageId: string, newContent: string) => {
    const originalMessage = nodeMap[messageId];
    if (!originalMessage) return;

    const parentId = originalMessage.parentId;

    // Create new sibling
    const newMessage: Message = {
      ...originalMessage,
      id: generateId(),
      content: newContent,
      timestamp: new Date(),
      tokenCount: estimateTokens(newContent),
      cost: estimateCost(estimateTokens(newContent), currentProvider, '', 'input'),
    };

    // Update tree
    const nextNodeMap = addChild(nodeMap, parentId || '', newMessage);
    setNodeMap(nextNodeMap);
    setCurrentLeafId(newMessage.id);

    // Calculate context for AI
    const history = getLinearHistory(nextNodeMap, newMessage.id);
    setMessages(history);

    setIsLoading(true);
    const startTime = Date.now();

    // Create assistant placeholder
    const assistantMessage: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      parentId: newMessage.id
    };

    const afterAssistantMap = addChild(nextNodeMap, newMessage.id, assistantMessage);
    setNodeMap(afterAssistantMap);
    setCurrentLeafId(assistantMessage.id);
    setMessages([...history, assistantMessage]);

    try {
      const finalResponse = await generateResponse(history, assistantMessage.id);
      const responseTime = Date.now() - startTime;
      const tokens = estimateTokens(finalResponse);
      const cost = estimateCost(tokens, currentProvider, '', 'output');

      const finalAssistant = {
        ...assistantMessage,
        content: finalResponse,
        responseTime,
        tokenCount: tokens,
        cost
      };

      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? finalAssistant : m));
      setNodeMap(prev => ({ ...prev, [assistantMessage.id]: finalAssistant }));
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? { ...m, content: `Error: ${errorMessage}` } : m));
    } finally {
      setIsLoading(false);
    }
  }, [nodeMap, currentProvider, generateResponse]);

  const handleBranchSwitch = useCallback((messageId: string, direction: 'prev' | 'next') => {
    const siblings = getBranchSiblings(nodeMap, messageId);
    const currentIndex = siblings.indexOf(messageId);

    let nextId = messageId;
    if (direction === 'prev' && currentIndex > 0) {
      nextId = siblings[currentIndex - 1];
    } else if (direction === 'next' && currentIndex < siblings.length - 1) {
      nextId = siblings[currentIndex + 1];
    }

    if (nextId !== messageId) {
      // Find the latest leaf for this branch
      let leaf = nextId;
      while (true) {
        const node = nodeMap[leaf];
        if (!node?.childrenIds || node.childrenIds.length === 0) break;
        leaf = node.childrenIds[node.childrenIds.length - 1];
      }

      setCurrentLeafId(leaf);
      setMessages(getLinearHistory(nodeMap, leaf));
    }
  }, [nodeMap]);

  const handleSelectNode = useCallback((nodeId: string) => {
    if (nodeMap[nodeId]) {
      setCurrentLeafId(nodeId);
      setMessages(getLinearHistory(nodeMap, nodeId));
      setActiveTab('chat');
    }
  }, [nodeMap, setActiveTab]);


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
      // Try modern clipboard API
      try {
        if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
          return true;
        }
      } catch {
        return false;
      }
      return false;
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

  return (
    <div className="flex flex-col h-full w-full">
      {/* Tab Header */}
      <div className="flex items-center border-b px-2 md:px-4 h-10 shrink-0 gap-2 md:gap-4 overflow-x-auto no-scrollbar">
        <button
          onClick={() => setActiveTab('chat')}
          className={cn(
            "flex items-center gap-2 h-full text-xs font-mono border-b-2 transition-colors px-2 shrink-0",
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
            "flex items-center gap-2 h-full text-xs font-mono border-b-2 transition-colors px-2 shrink-0",
            activeTab === 'artifacts'
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <FileText className="h-3 w-3" />
          ARTIFACTS {artifacts.length > 0 && `(${artifacts.length})`}
        </button>
        <button
          onClick={() => setActiveTab('tree')}
          className={cn(
            "flex items-center gap-2 h-full text-xs font-mono border-b-2 transition-colors px-2 shrink-0",
            activeTab === 'tree'
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <GitGraph className="h-3 w-3" />
          TREE
        </button>

        {totalTokens > 0 && (
          <div className="ml-auto hidden md:flex items-center gap-3 text-[10px] text-muted-foreground font-mono">
            <span>{totalTokens.toLocaleString()} tokens</span>
            {totalCost > 0 && <span>${totalCost.toFixed(4)}</span>}
          </div>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-hidden relative">
        <div
          className={cn("h-full flex flex-col", activeTab === 'chat' ? "flex" : "hidden")}
        >
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full px-4 py-8">
              <div className="text-center max-w-2xl w-full">
                <div className="overflow-x-auto my-8">
                  <pre className="text-muted-foreground text-xs md:text-sm font-mono leading-tight inline-block">
                    {JUNAS_ASCII_LOGO.split('\n').map((line, i) => (
                      <div
                        key={i}
                        className="animate-chunk-jiggle"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      >
                        {line}
                      </div>
                    ))}
                  </pre>
                </div>
                <p className="text-xs text-muted-foreground font-mono mt-6">v2.0.0</p>
              </div>
            </div>
          ) : (
            <MessageList
              messages={messages}
              nodeMap={nodeMap}
              isLoading={isLoading}
              onCopyMessage={handleCopyMessage}
              onRegenerateMessage={handleRegenerateMessage}
              onEditMessage={handleEditMessage}
              onBranchSwitch={handleBranchSwitch}
            />
          )}
        </div>

        <div
          className={cn("h-full bg-background", activeTab === 'artifacts' ? "block" : "hidden")}
        >
          <ArtifactsTab artifacts={artifacts} />
        </div>

        <div
          className={cn("h-full bg-background", activeTab === 'tree' ? "block" : "hidden")}
        >
          <TreeView
            nodeMap={nodeMap}
            currentLeafId={currentLeafId}
            onSelectNode={handleSelectNode}
          />
        </div>
      </div>

      {/* Input area */}
      <div className={cn("transition-all duration-200", (activeTab === 'artifacts' || activeTab === 'tree') ? "opacity-50 pointer-events-none" : "opacity-100")}>
        <MessageInput
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          currentProvider={currentProvider}
          onProviderChange={setCurrentProvider}
        />
      </div>

      {/* Legal Disclaimer Overlay */}
      <LegalDisclaimer />

      {/* Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={confirmation.isOpen}
        title={confirmation.title}
        description={confirmation.description}
        onConfirm={() => handleConfirmationResult(true)}
        onCancel={() => handleConfirmationResult(false)}
      />
    </div>
  );
}