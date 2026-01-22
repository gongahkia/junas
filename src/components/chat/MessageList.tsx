'use client';

import { useEffect, useRef, memo, useState } from 'react';
import { Message } from '@/types/chat';
import { FileText } from 'lucide-react';
import { StorageManager } from '@/lib/storage';
import { MermaidDiagram } from './MermaidDiagram';
import { ThinkingIndicator } from './ThinkingIndicator';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import remarkMath from 'remark-math';
import 'katex/dist/katex.min.css';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onCopyMessage: (content: string) => void;
  onRegenerateMessage: (messageId: string) => void;
  onEditMessage?: (messageId: string, newContent: string) => void;
  scrollToMessageId?: string;
}

// Memoized message item component to prevent unnecessary re-renders
const MessageItemComponent = ({
  message,
  onCopyMessage,
  onEditMessage
}: {
  message: Message;
  onCopyMessage: (content: string) => void;
  onEditMessage?: (messageId: string, newContent: string) => void;
}) => {
  const userName = StorageManager.getSettings().userName || 'User';
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [isEditing]);

  const handleSaveEdit = () => {
    if (editContent.trim() !== message.content) {
      onEditMessage?.(message.id, editContent);
    }
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditContent(message.content);
    setIsEditing(false);
  };

  return (
    <div
      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in-up`}
    >
      <div className={`flex w-full md:max-w-[80%] ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'} items-start gap-3`}>
        <div className={`flex-1 border ${
          message.role === 'user'
            ? 'bg-primary/5 border-primary/30'
            : 'bg-muted/20 border-muted-foreground/30'
        } font-mono overflow-hidden`}>
          <div className="space-y-3 px-4 py-3">
            {/* Attachments */}
            {message.attachments && message.attachments.length > 0 && (
              <div className="space-y-2">
                {message.attachments.map((attachment) => (
                  <div
                    key={attachment.id}
                    className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-background/60 text-sm text-foreground border-none"
                  >
                    <FileText className="w-4 h-4" />
                    <span className="truncate max-w-[320px]" title={attachment.name}>
                      {attachment.name}
                    </span>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {Math.round(attachment.size / 1024)}KB
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Message content */}
            <div className={`prose prose-sm md:prose-base max-w-none leading-relaxed`}>
              {isEditing ? (
                <div className="space-y-2">
                  <textarea
                    ref={textareaRef}
                    value={editContent}
                    onChange={(e) => {
                      setEditContent(e.target.value);
                      e.target.style.height = 'auto';
                      e.target.style.height = `${e.target.scrollHeight}px`;
                    }}
                    className="w-full bg-background/50 border border-input rounded-md p-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-ring resize-none"
                    rows={1}
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={handleCancelEdit}
                      className="px-2 py-1 text-xs bg-muted hover:bg-muted/80 text-muted-foreground rounded transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSaveEdit}
                      className="px-2 py-1 text-xs bg-primary text-primary-foreground hover:bg-primary/90 rounded transition-colors"
                    >
                      Save & Submit
                    </button>
                  </div>
                </div>
              ) : message.role === 'assistant' ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    code: ({ node, className, children, ...props }: any) => {
                      const match = /language-(\w+)/.exec(className || '');
                      const inline = !match;
                      const language = match?.[1];

                      // Handle diagram code blocks - always use Mermaid
                      const diagramLanguages = ['mermaid', 'diagram', 'plantuml', 'd2', 'graphviz', 'dot'];
                      if (!inline && language && diagramLanguages.includes(language)) {
                        const chartCode = String(children).trim();
                        return <MermaidDiagram chart={chartCode} />;
                      }

                      return !inline && match ? (
                        <pre className="bg-muted p-3 rounded-md overflow-x-auto">
                          <code className={className} {...props}>
                            {children}
                          </code>
                        </pre>
                      ) : (
                        <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
                          {children}
                        </code>
                      );
                    },
                    table: ({ children }) => (
                      <div className="overflow-x-auto">
                        <table className="min-w-full border-collapse border border-border">
                          {children}
                        </table>
                      </div>
                    ),
                    th: ({ children }) => (
                      <th className="border border-border px-3 py-2 bg-muted font-semibold text-left">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="border border-border px-3 py-2">
                        {children}
                      </td>
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              ) : (
                <p className="whitespace-pre-wrap">{message.content}</p>
              )}
            </div>

            {/* Citations */}
            {message.citations && message.citations.length > 0 && (
              <div className="space-y-1">
                <div className="text-xs font-semibold text-muted-foreground">Sources:</div>
                {message.citations.map((citation) => (
                  <a
                    key={citation.id}
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-xs text-primary hover:underline"
                  >
                    {citation.title}
                  </a>
                ))}
              </div>
            )}


            {/* Message actions */}
            {!isEditing && (
              <div className="flex items-center gap-1 pt-2 -mx-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onCopyMessage(message.content);
                  }}
                  className="text-xs px-2 py-1 text-muted-foreground/60 hover:text-foreground hover:bg-muted/30 transition-colors font-mono"
                  title="Copy message"
                >
                  [ Copy ]
                </button>
                {message.role === 'assistant' && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onRegenerateMessage(message.id);
                    }}
                    className="text-xs px-2 py-1 text-muted-foreground/60 hover:text-foreground hover:bg-muted/30 transition-colors font-mono"
                    title="Regenerate response"
                  >
                    [ Regenerate ]
                  </button>
                )}
                {message.role === 'user' && onEditMessage && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setIsEditing(true);
                    }}
                    className="text-xs px-2 py-1 text-muted-foreground/60 hover:text-foreground hover:bg-muted/30 transition-colors font-mono"
                    title="Edit message"
                  >
                    [ Edit ]
                  </button>
                )}
              </div>
            )}

            {/* Sender label */}
            <div className={`pt-2 text-[11px] font-medium text-muted-foreground/70 border-t border-muted-foreground/20 mt-3 ${
              message.role === 'user' ? 'text-right' : 'text-left'
            }`}>
              {message.role === 'assistant' ? '> Junas' : `> ${userName}`}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Custom comparison to prevent re-renders unless content actually changes
const arePropsEqual = (prevProps: any, nextProps: any) => {
  return (
    prevProps.message.id === nextProps.message.id &&
    prevProps.message.content === nextProps.message.content &&
    prevProps.message.responseTime === nextProps.message.responseTime
  );
};

const MessageItem = memo(MessageItemComponent, arePropsEqual);
MessageItem.displayName = 'MessageItem';

export const MessageList = memo(function MessageList({
  messages,
  isLoading,
  onCopyMessage,
  onRegenerateMessage,
  onEditMessage,
  scrollToMessageId
}: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const hasScrolledToMessage = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isAutoScrolling, setIsAutoScrolling] = useState(true);

  const scrollToBottom = (smooth = true) => {
    if (messagesEndRef.current && isAutoScrolling) {
      messagesEndRef.current.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' });
    }
  };

  // Scroll to specific message when scrollToMessageId changes
  useEffect(() => {
    if (scrollToMessageId && messageRefs.current[scrollToMessageId]) {
      hasScrolledToMessage.current = true;
      messageRefs.current[scrollToMessageId]?.scrollIntoView({ 
        behavior: 'smooth',
        block: 'center'
      });
      // Add highlight effect
      const element = messageRefs.current[scrollToMessageId];
      if (element) {
        element.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
        setTimeout(() => {
          element.classList.remove('ring-2', 'ring-primary', 'ring-offset-2');
        }, 2000);
      }
      // Reset the flag after a delay to allow normal scrolling again
      setTimeout(() => {
        hasScrolledToMessage.current = false;
      }, 2500);
    }
  }, [scrollToMessageId]);

  useEffect(() => {
    if (!scrollToMessageId && !hasScrolledToMessage.current) {
      scrollToBottom();
    }
  }, [messages, isLoading, scrollToMessageId]);

  if (messages.length === 0) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto px-4 md:px-8 py-8 md:py-12 space-y-6 md:space-y-8 max-w-5xl mx-auto w-full scroll-smooth"
    >
      {messages.map((message, index) => (
        <div
          key={message.id}
          ref={(el) => { messageRefs.current[message.id] = el; }}
        >
          {message.role === 'system' && message.content === 'loading' ? (
            <div className="flex justify-center py-4">
              <div className="text-sm text-muted-foreground/60 animate-pulse">
                Summarising your past conversation...
              </div>
            </div>
          ) : (
            <MessageItem
              message={message}
              onCopyMessage={onCopyMessage}
              onEditMessage={onEditMessage}
            />
          )}
        </div>
      ))}

      {/* ChatGPT-style thinking indicator */}
      {isLoading && <ThinkingIndicator />}

      <div ref={messagesEndRef} />
    </div>
  );
});
