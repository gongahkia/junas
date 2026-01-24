/**
 * Command processor for slash commands
 * Routes commands to either local NLP services or AI
 */

import {
  CommandType,
  COMMANDS,
  ProcessedCommand,
  LocalCommandResult,
  AsyncLocalCommandResult,
  CommandInfo,
} from './definitions';

export type {
  CommandType,
  ProcessedCommand,
  LocalCommandResult,
  AsyncLocalCommandResult,
  CommandInfo,
};
export { COMMANDS };

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

  const commandInfo = COMMANDS.find((c) => c.id === commandId);
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
  // Note: We need a way to check model status without importing the whole model-manager if possible
  // But for now, we'll keep the logic simple. The heavy lifting is the processing.
  // Ideally, isModelDownloaded should be lightweight.
  // For synchronous check, we assume the caller handles the model check or we assume it's okay to import simple helpers.
  // Actually, to fully optimize, we would need to dynamically import isModelDownloaded too, but that's async.
  // Since processLocalCommand is synchronous signature in the original code involving synchronous NLP,
  // we have to be careful.

  // Wait, extractEntities and analyzeDocument ARE synchronous.
  // We can't make processLocalCommand async if the caller expects sync for these.
  // But the original code imported them top-level.
  // To optimize, we MUST use CommonJS require or just accept that for THESE specific sync commands, we load the lib.
  // BUT: extractEntities uses `compromise`.
  // If we can't make this async, we can't dynamic import (await import).

  // Let's check how processLocalCommand is used.
  // It's used in ChatInterface: const syncResult = processLocalCommand(toolCommand);
  // If we change it to async, we need to update ChatInterface.
  // ChatInterface awaits `generateResponse` which is async.

  // Strategy:
  // 1. Convert `processLocalCommand` to allow returning a Promise OR make ChatInterface handle it.
  // 2. Actually, better: The synchronous commands (extract-entities, analyze-document) rely on `compromise`.
  //    If we want to lazy load `compromise`, we HAVE to make this async or use require() (which might break in strict ESM/Next.js edge cases, but usually fine in Webpack).

  // Let's assume we can change the signature or use require().
  // `require` is not available in standard ESM.

  // Let's look at ChatInterface again.
  // const syncResult = processLocalCommand(toolCommand);
  // It expects a result immediately.

  // If I proceed with this refactor, I should probably catch the need for async in ChatInterface.
  // However, I can cheat:
  // Since 'extract-entities' and 'analyze-document' are the only sync ones causing wide imports,
  // maybe I can just move them to be async too?
  // The original code had them return `LocalCommandResult` directly.

  // If I change the return type to `LocalCommandResult | Promise<LocalCommandResult>`, I break the interface.

  // Let's check `processAsyncLocalCommand`.
  // It handles the ONNX stuff which IS async.

  // Proposal:
  // Move `extract-entities` and `analyze-document` to `processAsyncLocalCommand`.
  // `processLocalCommand` will then just return "__ASYNC_MODEL_COMMAND__" for them too.
  // This allows ChatInterface to await the result in the async path.
  // This is the cleanest way to lazy load `compromise`.

  switch (commandType) {
    case 'extract-entities':
    case 'analyze-document':
    case 'summarize-local':
    case 'ner-advanced':
    case 'classify-text':
    case 'fetch-url':
    case 'web-search':
      return {
        success: true,
        content: '__ASYNC_MODEL_COMMAND__', // Signal to ChatInterface to use async processing
        requiresModel: requiresModel(commandType) || undefined,
      };

    case 'generate-document': {
      // This is purely string manipulation, can stay sync and lightweight
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
          type: type as any,
          content,
        },
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
 * Process a local command (async)
 */
export async function processAsyncLocalCommand(
  command: ProcessedCommand
): Promise<AsyncLocalCommandResult> {
  const { command: commandType, args } = command;

  try {
    switch (commandType) {
      case 'extract-entities': {
        const { extractEntities, formatEntityResults } = await import('@/lib/nlp/entity-extractor');
        const result = extractEntities(args);
        return {
          success: true,
          content: formatEntityResults(result),
        };
      }

      case 'analyze-document': {
        const { formatTextAnalysis } = await import('@/lib/nlp/text-analyzer');
        return {
          success: true,
          content: formatTextAnalysis(args),
        };
      }

      case 'summarize-local': {
        const { summarize } = await import('@/lib/ml/model-manager');
        const summary = await summarize(args);
        return {
          success: true,
          content: `**Summary:**\n\n${summary}`,
        };
      }

      case 'ner-advanced': {
        const { extractNamedEntities } = await import('@/lib/ml/model-manager');
        const entities = await extractNamedEntities(args);
        if (entities.length === 0) {
          return {
            success: true,
            content:
              '**Named Entity Recognition (BERT)**\n\nNo entities detected in the provided text.',
          };
        }
        const formatted = entities
          .map(
            (e: any) => `- **${e.word}** (${e.entity}) - confidence: ${(e.score * 100).toFixed(1)}%`
          )
          .join('\n');
        return {
          success: true,
          content: `**Named Entity Recognition (BERT)**\n\nFound ${entities.length} entities:\n\n${formatted}`,
        };
      }

      case 'classify-text': {
        const { classifyText } = await import('@/lib/ml/model-manager');
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
  const command = COMMANDS.find((c) => c.id === commandId);
  return command?.isLocal ?? false;
}

/**
 * Recursively resolve nested commands in a string.
 * Pattern: (/command args)
 * Replaces the pattern with the output of the command.
 */
export async function resolveCommandString(text: string): Promise<string> {
  const commandPattern = /\(\s*\/([\w-]+)(?:\s+([^)]*))?\s*\)/;
  let currentText = text;
  let match = currentText.match(commandPattern);
  let depth = 0;
  const MAX_DEPTH = 5; // Prevent infinite loops

  while (match && depth < MAX_DEPTH) {
    const fullMatch = match[0];
    const commandId = match[1] as CommandType;
    const args = match[2] || '';

    // Process the inner command
    const commandData: ProcessedCommand = {
      command: commandId,
      args: args.trim(),
      isLocal: isLocalCommand(commandId),
    };

    let result = '';

    // Try sync processing first
    const syncResult = processLocalCommand(commandData);

    if (syncResult.content === '__ASYNC_MODEL_COMMAND__') {
      const asyncResult = await processAsyncLocalCommand(commandData);
      result = asyncResult.success ? asyncResult.content : `[Error: ${asyncResult.content}]`;
    } else {
      result = syncResult.success ? syncResult.content : `[Error: ${syncResult.content}]`;
    }

    // Replace the matched pattern with the result
    currentText = currentText.replace(fullMatch, result);

    // Find next match
    match = currentText.match(commandPattern);
    depth++;
  }

  return currentText;
}
