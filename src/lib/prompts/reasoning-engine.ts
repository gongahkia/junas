/**
 * Multi-stage reasoning engine for complex legal queries
 * Implements self-critique, ReAct pattern, and advanced reasoning flows
 * Provider-agnostic implementation
 */

import { Message } from '@/types/chat';
import { QueryAnalysis } from './query-classifier';
import { getSelfCritiquePrompt, REACT_PATTERN_INSTRUCTIONS, getDefaultPromptConfig } from './system-prompts';

export interface ReasoningStage {
  stage: 'initial' | 'critique' | 'react' | 'final';
  prompt: string;
  response?: string;
  metadata?: Record<string, any>;
}

export interface ReasoningResult {
  stages: ReasoningStage[];
  finalResponse: string;
  totalTokensUsed?: number;
  reasoningTime?: number;
}

/**
 * Execute multi-stage reasoning for complex queries
 */
export class ReasoningEngine {
  /**
   * Process a query with multi-stage reasoning if needed
   */
  static async processQuery(
    query: string,
    analysis: QueryAnalysis,
    messages: Message[],
    apiCallFn: (messages: any[], config: any) => Promise<string>
  ): Promise<ReasoningResult> {
    const startTime = Date.now();
    const stages: ReasoningStage[] = [];

    // Stage 1: Initial analysis
    const initialStage = await this.executeInitialStage(
      query,
      analysis,
      messages,
      apiCallFn
    );
    stages.push(initialStage);

    let finalResponse = initialStage.response || '';

    // Stage 2: Self-critique (for deep/expert queries)
    if (analysis.useMultiStage && initialStage.response) {
      const critiqueStage = await this.executeCritiqueStage(
        query,
        initialStage.response,
        apiCallFn
      );
      stages.push(critiqueStage);
      finalResponse = critiqueStage.response || finalResponse;
    }

    // Stage 3: ReAct pattern (for expert queries)
    if (analysis.useReAct && finalResponse) {
      const reactStage = await this.executeReActStage(
        query,
        finalResponse,
        apiCallFn
      );
      stages.push(reactStage);
      finalResponse = reactStage.response || finalResponse;
    }

    const reasoningTime = Date.now() - startTime;

    return {
      stages,
      finalResponse,
      reasoningTime,
    };
  }

  /**
   * Execute initial analysis stage
   */
  private static async executeInitialStage(
    query: string,
    analysis: QueryAnalysis,
    messages: Message[],
    apiCallFn: (messages: any[], config: any) => Promise<string>
  ): Promise<ReasoningStage> {
    const config = getDefaultPromptConfig(analysis.reasoningDepth);

    const formattedMessages = messages.map(msg => ({
      role: msg.role,
      content: msg.content,
    }));

    const messagesWithSystem = [
      { role: 'system', content: config.systemPrompt },
      ...formattedMessages,
    ];

    const response = await apiCallFn(messagesWithSystem, {
      temperature: analysis.temperature,
      maxTokens: analysis.tokenBudget,
    });

    return {
      stage: 'initial',
      prompt: config.systemPrompt,
      response,
      metadata: {
        reasoningDepth: analysis.reasoningDepth,
        complexity: analysis.complexity,
      },
    };
  }

  /**
   * Execute self-critique stage
   */
  private static async executeCritiqueStage(
    originalQuery: string,
    initialResponse: string,
    apiCallFn: (messages: any[], config: any) => Promise<string>
  ): Promise<ReasoningStage> {
    const critiquePrompt = getSelfCritiquePrompt(originalQuery, initialResponse);

    const messages = [
      { role: 'system', content: 'You are a critical legal reviewer examining prior analysis for accuracy and completeness.' },
      { role: 'user', content: critiquePrompt },
    ];

    const response = await apiCallFn(messages, {
      temperature: 0.5,
      maxTokens: 4096,
    });

    return {
      stage: 'critique',
      prompt: critiquePrompt,
      response,
      metadata: {
        critiqueType: 'self-evaluation',
      },
    };
  }

  /**
   * Execute ReAct pattern stage for expert-level reasoning
   */
  private static async executeReActStage(
    originalQuery: string,
    previousResponse: string,
    apiCallFn: (messages: any[], config: any) => Promise<string>
  ): Promise<ReasoningStage> {
    const reactPrompt = `You previously analyzed this query using deep reasoning:

**Query:** ${originalQuery}

**Your Analysis:** ${previousResponse}

Now, apply the ReAct (Reasoning + Acting) pattern to verify and enhance your analysis:

${REACT_PATTERN_INSTRUCTIONS}

Go through at least 2-3 reasoning cycles, examining:
- Missing considerations
- Alternative interpretations
- Practical implications
- Strategic recommendations

Provide your final, refined analysis.`;

    const messages = [
      {
        role: 'system',
        content: 'You are an expert legal strategist using iterative reasoning to refine complex legal analysis.',
      },
      { role: 'user', content: reactPrompt },
    ];

    const response = await apiCallFn(messages, {
      temperature: 0.7,
      maxTokens: 6144,
    });

    return {
      stage: 'react',
      prompt: reactPrompt,
      response,
      metadata: {
        patternType: 'ReAct',
      },
    };
  }

  /**
   * Format multi-stage response for display
   */
  static formatMultiStageResponse(result: ReasoningResult, showStages: boolean = true): string {
    if (!showStages || result.stages.length === 1) {
      return result.finalResponse;
    }

    let formatted = '';

    // Add reasoning process indicator
    if (result.stages.length > 1) {
      formatted += `> **🧠 Multi-Stage Reasoning Applied** (${result.stages.length} stages, ${(result.reasoningTime! / 1000).toFixed(1)}s)\n\n`;
    }

    // Show initial analysis
    const initialStage = result.stages.find(s => s.stage === 'initial');
    if (initialStage?.response) {
      if (result.stages.length > 1) {
        formatted += `<details>\n<summary>📊 Stage 1: Initial Analysis</summary>\n\n${initialStage.response}\n\n</details>\n\n`;
      }
    }

    // Show critique stage
    const critiqueStage = result.stages.find(s => s.stage === 'critique');
    if (critiqueStage?.response) {
      formatted += `<details>\n<summary>🔍 Stage 2: Self-Critique & Refinement</summary>\n\n${critiqueStage.response}\n\n</details>\n\n`;
    }

    // Show ReAct stage
    const reactStage = result.stages.find(s => s.stage === 'react');
    if (reactStage?.response) {
      formatted += `<details>\n<summary>⚡ Stage 3: Expert ReAct Analysis</summary>\n\n${reactStage.response}\n\n</details>\n\n`;
    }

    // Add final response header
    formatted += `---\n\n## 🎯 Final Refined Analysis\n\n${result.finalResponse}`;

    return formatted;
  }

  /**
   * Create reasoning summary for UI display
   */
  static createReasoningSummary(analysis: QueryAnalysis, result: ReasoningResult): string {
    const parts = [
      `**Complexity:** ${analysis.complexity.toUpperCase()}`,
      `**Reasoning Depth:** ${analysis.reasoningDepth}`,
      `**Stages:** ${result.stages.length}`,
    ];

    if (result.reasoningTime) {
      parts.push(`**Time:** ${(result.reasoningTime / 1000).toFixed(1)}s`);
    }

    return parts.join(' • ');
  }
}

export interface ThinkingStageData {
  stage: 'initial' | 'critique' | 'react';
  content: string;
  label: string;
  isComplete?: boolean;
  isStreaming?: boolean;
}

/**
 * Streaming wrapper for multi-stage reasoning
 * Allows streaming of each stage separately
 */
export class StreamingReasoningEngine {
  /**
   * Process query with streaming support for each stage
   */
  static async processQueryStreaming(
    query: string,
    analysis: QueryAnalysis,
    messages: Message[],
    apiCallFn: (messages: any[], config: any, onChunk?: (chunk: string) => void) => Promise<string>,
    onStageStart?: (stage: string, stageNumber: number, totalStages: number) => void,
    onChunk?: (chunk: string) => void,
    onThinkingStage?: (stage: ThinkingStageData) => void
  ): Promise<ReasoningResult> {
    const startTime = Date.now();
    const stages: ReasoningStage[] = [];

    // Calculate total stages
    const totalStages = 1 + (analysis.useMultiStage ? 1 : 0) + (analysis.useReAct ? 1 : 0);
    let currentStage = 0;
    const isMultiStage = totalStages > 1;

    // Stage 1: Initial analysis
    currentStage++;
    if (onStageStart) {
      onStageStart('initial', currentStage, totalStages);
    }

    const config = getDefaultPromptConfig(analysis.reasoningDepth);
    const formattedMessages = messages.map(msg => ({
      role: msg.role,
      content: msg.content,
    }));

    const messagesWithSystem = [
      { role: 'system', content: config.systemPrompt },
      ...formattedMessages,
    ];

    let initialResponse = '';

    // For multi-stage, don't stream initial stage to main output
    // For single stage, stream to main output
    const response1 = await apiCallFn(
      messagesWithSystem,
      {
        temperature: analysis.temperature,
        maxTokens: analysis.tokenBudget,
      },
      isMultiStage ? undefined : onChunk  // Only stream if it's the final stage
    );
    initialResponse = response1;

    stages.push({
      stage: 'initial',
      prompt: config.systemPrompt,
      response: initialResponse,
      metadata: { reasoningDepth: analysis.reasoningDepth },
    });

    // If multi-stage, send initial as thinking stage
    if (isMultiStage && onThinkingStage && initialResponse) {
      onThinkingStage({
        stage: 'initial',
        content: initialResponse,
        label: 'Initial Analysis'
      });
    }

    let finalResponse = initialResponse;

    // Stage 2: Self-critique
    if (analysis.useMultiStage) {
      currentStage++;
      const isFinalStage = !analysis.useReAct;

      if (onStageStart) {
        onStageStart('critique', currentStage, totalStages);
      }

      const critiquePrompt = getSelfCritiquePrompt(query, initialResponse);
      const critiqueMessages = [
        {
          role: 'system',
          content: 'You are a critical legal reviewer examining prior analysis for accuracy and completeness.',
        },
        { role: 'user', content: critiquePrompt },
      ];

      const response2 = await apiCallFn(
        critiqueMessages,
        { temperature: 0.5, maxTokens: 4096 },
        isFinalStage ? onChunk : undefined  // Only stream if it's the final stage
      );

      stages.push({
        stage: 'critique',
        prompt: critiquePrompt,
        response: response2,
      });

      // If not final stage, send as thinking
      if (!isFinalStage && onThinkingStage && response2) {
        onThinkingStage({
          stage: 'critique',
          content: response2,
          label: 'Self-Critique & Refinement'
        });
      }

      finalResponse = response2;
    }

    // Stage 3: ReAct (always the final stage if present)
    if (analysis.useReAct) {
      currentStage++;
      if (onStageStart) {
        onStageStart('react', currentStage, totalStages);
      }

      const reactPrompt = `Apply ReAct pattern to this query and previous analysis:

**Query:** ${query}

**Previous Analysis:** ${finalResponse}

${REACT_PATTERN_INSTRUCTIONS}

Provide your final, refined analysis with strategic insights.`;

      const reactMessages = [
        {
          role: 'system',
          content: 'You are an expert legal strategist using iterative reasoning.',
        },
        { role: 'user', content: reactPrompt },
      ];

      const response3 = await apiCallFn(
        reactMessages,
        { temperature: 0.7, maxTokens: 6144 },
        onChunk  // Always stream to main output as this is the final stage
      );

      stages.push({
        stage: 'react',
        prompt: reactPrompt,
        response: response3,
      });

      finalResponse = response3;
    }

    const reasoningTime = Date.now() - startTime;

    return {
      stages,
      finalResponse,
      reasoningTime,
    };
  }
}
