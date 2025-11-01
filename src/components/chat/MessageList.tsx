'use client';

import { useEffect, useRef, memo } from 'react';
import { Message, ThinkingStage } from '@/types/chat';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Copy, Download, FileText, User, Bot, Loader2 } from 'lucide-react';
import { ReasoningIndicator } from './ReasoningIndicator';
import { ThinkingStages } from './ThinkingStages';
import { TokenCounter } from './TokenCounter';
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
  currentThinkingStages?: ThinkingStage[];
}

// Memoized message item component to prevent unnecessary re-renders
const MessageItem = memo(({
  message,
  onCopyMessage
}: {
  message: Message;
  onCopyMessage: (content: string) => void;
}) => {
  return (
    <div
      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`flex w-full md:max-w-[85%] ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'} items-start space-x-3`}>
        <Card className={`p-3 md:p-4 ${
          message.role === 'user'
            ? 'bg-card text-card-foreground border border-border'
            : 'bg-card text-card-foreground border border-border'
        }`}>
          <div className="space-y-3">
            {/* Attachments */}
            {message.attachments && message.attachments.length > 0 && (
              <div className="space-y-2">
                {message.attachments.map((attachment) => (
                  <div
                    key={attachment.id}
                    className="inline-flex items-center space-x-2 px-2 md:px-3 py-1.5 rounded-md bg-muted text-xs md:text-sm text-foreground border border-border"
                  >
                    <FileText className="w-3 h-3 md:w-4 md:h-4" />
                    <span className="truncate max-w-[200px] md:max-w-[320px]" title={attachment.name}>
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
            <div className={`prose prose-sm max-w-none`}>
              {message.role === 'assistant' ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    code: ({ node, className, children, ...props }: any) => {
                      const match = /language-(\w+)/.exec(className || '');
                      const inline = !match;
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

            {/* Reasoning indicator for assistant messages */}
            {message.role === 'assistant' && message.reasoning && (
              <div className="pt-2">
                <ReasoningIndicator
                  complexity={message.reasoning.complexity}
                  reasoningDepth={message.reasoning.reasoningDepth}
                  stage={message.reasoning.stages > 1 ? 'complete' : undefined}
                  totalStages={message.reasoning.stages}
                />
              </div>
            )}

            {/* Token counter for all messages */}
            <div className="pt-2">
              <TokenCounter content={message.content} responseTime={message.responseTime} />
            </div>

            {/* Message actions */}
            <div className="flex items-center space-x-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onCopyMessage(message.content)}
                className={`h-8 px-2 text-muted-foreground hover:bg-muted`}
              >
                <Copy className="w-3 h-3" />
                <span className="sr-only">Copy message</span>
              </Button>
            </div>
          </div>
          {/* Sender label */}
          <div className={`pt-2 text-[10px] text-muted-foreground ${
            message.role === 'user' ? 'text-right' : 'text-left'
          }`}>
            {message.role === 'assistant' ? 'Junas' : 'User'}
          </div>
        </Card>
      </div>
    </div>
  );
});

MessageItem.displayName = 'MessageItem';

export const MessageList = memo(function MessageList({
  messages,
  isLoading,
  onCopyMessage,
  onRegenerateMessage,
  currentThinkingStages
}: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, currentThinkingStages]);

  if (messages.length === 0) {
    return null;
  }

  return (
    <div className="flex-1 overflow-y-auto px-3 md:px-6 py-4 md:py-8 space-y-4 md:space-y-6 max-w-6xl mx-auto w-full">
      {messages.map((message, index) => (
        <div key={message.id}>
          {/* Show thinking stages if this message has them */}
          {message.role === 'assistant' && message.thinkingStages && message.thinkingStages.length > 0 && (
            <ThinkingStages stages={message.thinkingStages} />
          )}

          <MessageItem
            message={message}
            onCopyMessage={onCopyMessage}
          />
        </div>
      ))}

      {/* Show live thinking stages during streaming */}
      {isLoading && currentThinkingStages && currentThinkingStages.length > 0 && (
        <ThinkingStages stages={currentThinkingStages} />
      )}

      {/* Enhanced loading indicator */}
      {isLoading && (
        <div className="flex justify-start">
          <div className="flex items-start space-x-2 w-full md:max-w-[85%]">
            <Card className="p-3 md:p-4">
              <div className="flex items-center space-x-2 md:space-x-3">
                <Loader2 className="w-4 h-4 md:w-5 md:h-5 animate-spin text-primary flex-shrink-0" />
                <div className="space-y-1">
                  <span className="text-xs md:text-sm font-medium">Junas is analyzing your request...</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                    <div className="w-2 h-2 bg-primary rounded-full animate-pulse delay-75" />
                    <div className="w-2 h-2 bg-primary rounded-full animate-pulse delay-150" />
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
});
