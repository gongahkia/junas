/**
 * Command processor for slash commands
 * Routes commands to either local NLP services or AI
 */

import { extractEntities, formatEntityResults } from '@/lib/nlp/entity-extractor';
import { formatTextAnalysis } from '@/lib/nlp/text-analyzer';
import {
  isModelDownloaded,
  summarize,
  extractNamedEntities,
  classifyText,
} from '@/lib/ml/model-manager';

export type CommandType =
  | 'extract-entities'
  | 'analyze-document'
  | 'summarize-local'
  | 'ner-advanced'
  | 'classify-text'
  | 'search-case-law'
  | 'research-statute'
  | 'analyze-contract'
  | 'summarize-document'
  | 'draft-clause'
  | 'check-compliance'
  | 'due-diligence-review';

export interface CommandInfo {
  id: CommandType;
  label: string;
  description: string;
  isLocal: boolean; // true = processed locally, false = requires AI
}

export const COMMANDS: CommandInfo[] = [
  {
    id: 'extract-entities',
    label: 'extract-entities',
    description: 'Identify persons, organizations, dates, and legal references (Local)',
    isLocal: true,
  },
  {
    id: 'analyze-document',
    label: 'analyze-document',
    description: 'Get document statistics, readability, and structure (Local)',
    isLocal: true,
  },
  {
    id: 'summarize-local',
    label: 'summarize-local',
    description: 'Summarize text using local ONNX model (requires download)',
    isLocal: true,
  },
  {
    id: 'ner-advanced',
    label: 'ner-advanced',
    description: 'Advanced NER using BERT model (requires download)',
    isLocal: true,
  },
  {
    id: 'classify-text',
    label: 'classify-text',
    description: 'Classify text sentiment using local model (requires download)',
    isLocal: true,
  },
  {
    id: 'search-case-law',
    label: 'search-case-law',
    description: 'Search Singapore legal database for relevant cases',
    isLocal: false,
  },
  {
    id: 'research-statute',
    label: 'research-statute',
    description: 'Look up statutory provisions and interpretations',
    isLocal: false,
  },
  {
    id: 'analyze-contract',
    label: 'analyze-contract',
    description: 'Extract key terms, obligations, and risks from contract',
    isLocal: false,
  },
  {
    id: 'summarize-document',
    label: 'summarize-document',
    description: 'Generate concise summary of legal document',
    isLocal: false,
  },
  {
    id: 'draft-clause',
    label: 'draft-clause',
    description: 'Generate legal clause based on requirements',
    isLocal: false,
  },
  {
    id: 'check-compliance',
    label: 'check-compliance',
    description: 'Verify regulatory compliance for Singapore law',
    isLocal: false,
  },
  {
    id: 'due-diligence-review',
    label: 'due-diligence-review',
    description: 'Conduct legal due diligence checklist',
    isLocal: false,
  },
];

export interface ProcessedCommand {
  command: CommandType;
  args: string;
  isLocal: boolean;
}

export interface LocalCommandResult {
  success: boolean;
  content: string;
}

/**
 * Parse a message to detect if it contains a slash command
 */
export function parseCommand(message: string): ProcessedCommand | null {
  const commandPattern = /^\/([a-z-]+)\s*([\s\S]*)/i;
  const match = message.trim().match(commandPattern);

  if (!match) {
    return null;
  }

  const commandId = match[1].toLowerCase() as CommandType;
  const args = match[2].trim();

  const commandInfo = COMMANDS.find(c => c.id === commandId);
  if (!commandInfo) {
    return null;
  }

  return {
    command: commandId,
    args,
    isLocal: commandInfo.isLocal,
  };
}

/**
 * Process a local command (no AI required)
 */
export function processLocalCommand(command: ProcessedCommand): LocalCommandResult {
  const { command: commandType, args } = command;

  if (!args || args.trim().length === 0) {
    return {
      success: false,
      content: `Please provide text after the /${commandType} command.\n\nExample:\n\`/${commandType} [your text here]\``,
    };
  }

  switch (commandType) {
    case 'extract-entities': {
      const result = extractEntities(args);
      return {
        success: true,
        content: formatEntityResults(result),
      };
    }

    case 'analyze-document': {
      return {
        success: true,
        content: formatTextAnalysis(args),
      };
    }

    default:
      return {
        success: false,
        content: `Command /${commandType} is not a local command.`,
      };
  }
}

/**
 * Check if a command should be processed locally
 */
export function isLocalCommand(commandId: string): boolean {
  const command = COMMANDS.find(c => c.id === commandId);
  return command?.isLocal ?? false;
}
