'use client';

import { useState, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';
import { Send, Paperclip, X, FileText, Image } from 'lucide-react';
import { FileAttachment } from '@/types/chat';
import { useToast } from '@/components/ui/toast';
import { formatFileSize } from '@/lib/utils';

interface MessageInputProps {
  onSendMessage: (content: string, attachments?: FileAttachment[]) => void;
  onFileUpload: (files: File[]) => Promise<FileAttachment[]>;
  isLoading: boolean;
  placeholder?: string;
}

export function MessageInput({ 
  onSendMessage, 
  onFileUpload, 
  isLoading, 
  placeholder = "Ask Junas anything about Singapore law..." 
}: MessageInputProps) {
  const [message, setMessage] = useState('');
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { addToast } = useToast();

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isLoading) return;

    onSendMessage(message.trim(), attachments);
    setMessage('');
    setAttachments([]);
  }, [message, attachments, isLoading, onSendMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }, [handleSubmit]);

  const handleFileSelect = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const fileArray = Array.from(files);
    const maxFiles = 3;
    const maxSize = 10 * 1024 * 1024; // 10MB

    // Validate files
    const validFiles = fileArray.filter(file => {
      if (file.size > maxSize) {
        addToast({
          type: 'error',
          title: 'File Too Large',
          description: `File ${file.name} is too large. Maximum size is 10MB.`,
          duration: 5000,
        });
        return false;
      }
      return true;
    }).slice(0, maxFiles);

    if (validFiles.length === 0) return;

    setIsUploading(true);
    try {
      const newAttachments = await onFileUpload(validFiles);
      setAttachments(prev => [...prev, ...newAttachments]);
    } catch (error) {
      console.error('File upload failed:', error);
      addToast({
        type: 'error',
        title: 'Upload Failed',
        description: 'Failed to upload files. Please try again.',
        duration: 5000,
      });
    } finally {
      setIsUploading(false);
    }
  }, [onFileUpload]);

  const removeAttachment = useCallback((attachmentId: string) => {
    setAttachments(prev => prev.filter(att => att.id !== attachmentId));
  }, []);

  const getFileIcon = (type: string) => {
    if (type.startsWith('image/')) return Image;
    return FileText;
  };

  return (
    <div className="border-t bg-background">
      <div className="max-w-6xl mx-auto px-6 py-6">
        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="mb-4 space-y-2">
            {attachments.map((attachment) => {
              const Icon = getFileIcon(attachment.type);
              return (
                <div
                  key={attachment.id}
                  className="flex items-center space-x-2 p-2 bg-muted rounded-md"
                >
                  <Icon className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm flex-1 truncate">{attachment.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatFileSize(attachment.size)}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeAttachment(attachment.id)}
                    className="h-6 w-6 p-0"
                  >
                    <X className="w-3 h-3" />
                  </Button>
                </div>
              );
            })}
          </div>
        )}

        {/* Input form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex items-end space-x-2">
            <div className="flex-1">
              <Textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={isLoading}
                className="min-h-[80px] max-h-[300px] resize-none"
                rows={1}
              />
            </div>
            
            <div className="flex flex-col space-y-2">
              {/* File upload button */}
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading || isUploading || attachments.length >= 3}
                className="h-10 w-10"
              >
                <Paperclip className="h-4 w-4" />
                <span className="sr-only">Attach files</span>
              </Button>

              {/* Send button */}
              <Button
                type="submit"
                disabled={!message.trim() || isLoading || isUploading}
                className="h-10 w-10"
              >
                <Send className="h-4 w-4" />
                <span className="sr-only">Send message</span>
              </Button>
            </div>
          </div>

          {/* File input (hidden) */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.jpg,.jpeg,.png,.gif,.bmp,.webp"
            onChange={(e) => handleFileSelect(e.target.files)}
            className="hidden"
          />

          {/* Upload status */}
          {isUploading && (
            <div className="text-sm text-muted-foreground text-center">
              Processing files...
            </div>
          )}

          {/* Help text */}
          <div className="text-xs text-muted-foreground text-center">
            Press Enter to send, Shift+Enter for new line. 
            Supports PDF, DOCX, and image files (max 3 files, 10MB each).
          </div>
        </form>
      </div>
    </div>
  );
}
