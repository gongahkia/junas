export interface Attachment {
  id: string;
  name: string;
  size: number;
  type?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  citations?: Citation[];
  attachments?: Attachment[];
  responseTime?: number; // Time in milliseconds
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
  userName?: string;
  userRole?: string;
  userPurpose?: string;
}

export type DiagramRenderer = 'mermaid' | 'plantuml' | 'graphviz' | 'd2';
