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
  | 'due-diligence-review'
  | 'generate-document'
  | 'fetch-url'
  | 'web-search';

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
  {
    id: 'generate-document',
    label: 'generate-document',
    description: 'Generate a downloadable text or markdown document',
    isLocal: true, // Processed locally to save the artifact
  },
  {
    id: 'fetch-url',
    label: 'fetch-url',
    description: 'Fetch and extract text content from a URL',
    isLocal: true,
  },
  {
    id: 'web-search',
    label: 'web-search',
    description: 'Search the web for information',
    isLocal: true,
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
  requiresModel?: string; // Model ID required for this command
  artifact?: {
    title: string;
    type: 'text' | 'markdown';
    content: string;
  };
}

export interface AsyncLocalCommandResult {
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
 * Check if a command requires an ONNX model
 */
export function requiresModel(commandType: CommandType): string | null {
  const modelMap: Partial<Record<CommandType, string>> = {
    'summarize-local': 'summarization',
    'ner-advanced': 'ner',
    'classify-text': 'text-classification',
  };
  return modelMap[commandType] || null;
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

  // Check if this command requires a model
  const requiredModel = requiresModel(commandType);
  if (requiredModel) {
    if (!isModelDownloaded(requiredModel)) {
      return {
        success: false,
        content: `This command requires the "${requiredModel}" model to be downloaded.\n\nGo to ⚙ Configuration → Models to download it.`,
        requiresModel: requiredModel,
      };
    }
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

    case 'generate-document': {
      // Expected args: JSON string or formatted text
      // Try to parse JSON first
      let title = 'Generated Document';
      let type: 'text' | 'markdown' = 'markdown';
      let content = args;

      try {
        // Try to find JSON-like structure
        const jsonMatch = args.match(/({[\s\S]*})/);
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[1]);
          if (parsed.title) title = parsed.title;
          if (parsed.type) type = parsed.type;
          if (parsed.content) content = parsed.content;
        } else {
            // If not JSON, try to extract title from first line if it starts with #
            const lines = args.split('\n');
            if (lines.length > 0 && lines[0].startsWith('#')) {
                title = lines[0].replace(/^#+\s*/, '').trim();
            }
        }
      } catch (e) {
        // Fallback to using raw args as content
        console.warn('Failed to parse generate-document args as JSON', e);
      }

      return {
        success: true,
        content: `Document "${title}" generated successfully. Check the Artifacts tab.`,
        artifact: {
            title,
            type,
            content
        }
      };
    }

    // ONNX model commands return a placeholder - actual processing is async
    case 'summarize-local':
    case 'ner-advanced':
    case 'classify-text':
    case 'fetch-url':
    case 'web-search':
      return {
        success: true,
        content: '__ASYNC_MODEL_COMMAND__', // Signal to ChatInterface to use async processing
        requiresModel: requiredModel || undefined,
      };

    default:
      return {
        success: false,
        content: `Command /${commandType} is not a local command.`,
      };
  }
}

/**
 * Process a local command that requires an ONNX model (async)
 */
export async function processAsyncLocalCommand(command: ProcessedCommand): Promise<AsyncLocalCommandResult> {
  const { command: commandType, args } = command;

  try {
    switch (commandType) {
      case 'summarize-local': {
        const summary = await summarize(args);
        return {
          success: true,
          content: `**Summary:**\n\n${summary}`,
        };
      }

      case 'ner-advanced': {
        const entities = await extractNamedEntities(args);
        if (entities.length === 0) {
          return {
            success: true,
            content: '**Named Entity Recognition (BERT)**\n\nNo entities detected in the provided text.',
          };
        }
        const formatted = entities
          .map(e => `- **${e.word}** (${e.entity}) - confidence: ${(e.score * 100).toFixed(1)}%`)
          .join('\n');
        return {
          success: true,
          content: `**Named Entity Recognition (BERT)**\n\nFound ${entities.length} entities:\n\n${formatted}`,
        };
      }

      case 'classify-text': {
        const classifications = await classifyText(args);
        const top = classifications[0];
        return {
          success: true,
          content: `**Text Classification**\n\nSentiment: **${top.label}**\nConfidence: ${(top.score * 100).toFixed(1)}%`,
        };
      }

      case 'fetch-url': {
        try {
          const response = await fetch('/api/tools/fetch-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: args }),
          });

          const data = await response.json();

          if (!response.ok) {
             return {
              success: false,
              content: `Error fetching URL: ${data.error || response.statusText}`,
            };
          }

          return {
            success: true,
            content: `**Fetched Content from ${args}:**\n\n${data.content}`,
          };
        } catch (e: any) {
           return {
              success: false,
              content: `Network error: ${e.message}`,
            };
        }
      }

      case 'web-search': {
        try {
          const response = await fetch('/api/tools/web-search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: args }),
          });

          const data = await response.json();

          if (!response.ok) {
             return {
              success: false,
              content: `Error searching web: ${data.error || response.statusText}`,
            };
          }

          let resultText = `**Web Search Results for "${args}":**\n\n`;
          if (data.results && data.results.length > 0) {
              data.results.forEach((r: any, i: number) => {
                  resultText += `${i + 1}. **[${r.title}](${r.link})**\n${r.snippet}\n\n`;
              });
              if (data.warning) {
                  resultText += `\n*Note: ${data.warning}*`;
              }
          } else {
              resultText += 'No results found.';
          }

          return {
            success: true,
            content: resultText,
          };
        } catch (e: any) {
           return {
              success: false,
              content: `Network error: ${e.message}`,
            };
        }
      }

      default:
        return {
          success: false,
          content: `Command /${commandType} does not support async processing.`,
        };
    }
  } catch (error: any) {
    return {
      success: false,
      content: `Error processing command: ${error.message}`,
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
