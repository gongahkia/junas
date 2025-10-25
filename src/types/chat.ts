export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  attachments?: FileAttachment[];
  toolCalls?: ToolCall[];
  citations?: Citation[];
}

export interface FileAttachment {
  id: string;
  name: string;
  type: string;
  size: number;
  content?: string; // Extracted text content
  preview?: string; // Base64 preview for images
}

export interface ToolCall {
  id: string;
  name: string;
  parameters: Record<string, any>;
  result?: any;
  status: 'pending' | 'success' | 'error';
}

export interface Citation {
  id: string;
  title: string;
  url: string;
  type: 'case' | 'statute' | 'regulation' | 'article';
  jurisdiction?: string;
  year?: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  currentProvider: string;
  apiKeys: Record<string, string>;
  settings: ChatSettings;
}

export interface ChatSettings {
  temperature: number;
  maxTokens: number;
  systemPrompt: string;
  autoSave: boolean;
  darkMode: boolean;
}
