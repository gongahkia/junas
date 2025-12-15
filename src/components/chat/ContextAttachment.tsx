'use client';

import { useState, useRef } from 'react';
import {
  X,
  FileText,
  Image as ImageIcon,
  File
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { validateFile } from '@/lib/file-processing';

export interface AttachedFile {
  id: string;
  name: string;
  type: string;
  size: number;
  content: string;
  preview?: string;
}

interface ContextAttachmentProps {
  onFilesAttach: (files: AttachedFile[]) => void;
  attachedFiles: AttachedFile[];
  onFileRemove: (fileId: string) => void;
  disabled?: boolean;
}

export function ContextAttachment({ 
  onFilesAttach, 
  attachedFiles, 
  onFileRemove,
  disabled = false 
}: ContextAttachmentProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setIsProcessing(true);

    try {
      const processedFiles: AttachedFile[] = [];
      const errors: string[] = [];

      for (const file of Array.from(files)) {
        // Validate file
        const validation = validateFile(file);
        if (!validation.valid) {
          errors.push(`${file.name}: ${validation.error}`);
          continue;
        }

        const content = await readFileContent(file);
        
        processedFiles.push({
          id: `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`,
          name: file.name,
          type: file.type,
          size: file.size,
          content,
          preview: await generatePreview(file, content),
        });
      }

      if (errors.length > 0) {
        alert(`Some files could not be uploaded:\n${errors.join('\n')}`);
      }

      if (processedFiles.length > 0) {
        onFilesAttach(processedFiles);
        setIsOpen(false);
      }
    } catch (error) {
      console.error('Error processing files:', error);
      alert('Error processing files. Please try again.');
    } finally {
      setIsProcessing(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        const result = e.target?.result;
        if (typeof result === 'string') {
          resolve(result);
        } else {
          reject(new Error('Failed to read file as text'));
        }
      };
      
      reader.onerror = () => reject(new Error('File reading failed'));
      
      // Read as text for text files, data URL for images
      if (file.type.startsWith('image/')) {
        reader.readAsDataURL(file);
      } else {
        reader.readAsText(file);
      }
    });
  };

  const generatePreview = async (file: File, content: string): Promise<string> => {
    if (file.type.startsWith('image/')) {
      return content; // Data URL for images
    }
    
    // For text files, return first 200 characters
    if (file.type.startsWith('text/') || 
        file.type === 'application/json' ||
        file.type === 'application/pdf') {
      return content.slice(0, 200);
    }
    
    return '';
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const getFileIcon = (type: string) => {
    if (type.startsWith('image/')) return <ImageIcon className="h-4 w-4" />;
    if (type.startsWith('text/') || type === 'application/json') return <FileText className="h-4 w-4" />;
    return <File className="h-4 w-4" />;
  };

  return (
    <>
      {/* Attach button */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        disabled={disabled}
        className="text-xs hover:bg-accent px-2 py-1 transition-colors font-mono disabled:opacity-50"
        title="Add context"
      >
        [ 📎 ]
      </button>

      {/* Attached files display */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {attachedFiles.map((file) => (
            <div
              key={file.id}
              className="flex items-center gap-2 bg-muted rounded-md px-2 py-1.5 text-sm border"
            >
              <div className="text-muted-foreground">
                {getFileIcon(file.type)}
              </div>
              <span className="font-medium truncate max-w-[150px]">
                {file.name}
              </span>
              <span className="text-xs text-muted-foreground">
                {formatFileSize(file.size)}
              </span>
              <button
                onClick={() => onFileRemove(file.id)}
                className="text-muted-foreground hover:text-foreground transition-colors"
                title="Remove file"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* File upload dialog */}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md font-mono">
          <DialogHeader>
            <DialogTitle className="text-sm">[ 📎 Add Context ]</DialogTitle>
            <DialogDescription className="text-xs">
              Upload documents, images, or text files to provide context for your question.
              Supported formats: PDF, TXT, JSON, DOC, DOCX, images.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* File input */}
            <div className="border border-muted-foreground/30 bg-muted/10 p-8 text-center">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".txt,.pdf,.doc,.docx,.json,.png,.jpg,.jpeg,.gif,.webp"
                onChange={handleFileSelect}
                className="hidden"
                id="file-upload"
                disabled={isProcessing}
              />
              <label
                htmlFor="file-upload"
                className="cursor-pointer flex flex-col items-center gap-2 text-xs"
              >
                {isProcessing ? (
                  <>
                    <span className="text-2xl">⏳</span>
                    <span className="text-muted-foreground">
                      [ Processing files... ]
                    </span>
                  </>
                ) : (
                  <>
                    <span className="font-medium">
                      Click to upload files
                    </span>
                    <span className="text-muted-foreground">
                      or drag and drop files here
                    </span>
                  </>
                )}
              </label>
            </div>

            {/* Current attachments preview */}
            {attachedFiles.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-medium">&gt; Currently attached:</h4>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {attachedFiles.map((file) => (
                    <div
                      key={file.id}
                      className="flex items-start gap-2 p-2 border border-muted-foreground/30 bg-muted/10 text-xs"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">
                          {file.name}
                        </div>
                        <div className="text-muted-foreground">
                          {formatFileSize(file.size)}
                        </div>
                      </div>
                      <button
                        onClick={() => onFileRemove(file.id)}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                        title="Remove file"
                      >
                        [ X ]
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tips */}
            <div className="text-xs text-muted-foreground space-y-1 bg-muted/10 p-3 border border-muted-foreground/30">
              <p className="font-medium">&gt; Tips:</p>
              <ul className="space-y-0.5 ml-4">
                <li>• Attach contracts for clause analysis</li>
                <li>• Upload case documents for fact extraction</li>
                <li>• Include relevant statutes for compliance checks</li>
                <li>• Max file size: 10MB per file</li>
              </ul>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
