/**
 * Query complexity classifier for determining appropriate reasoning depth
 * Provider-agnostic implementation
 */

import { QueryComplexity, ReasoningDepth } from './system-prompts';

interface ComplexityIndicators {
  multipleQuestions: boolean;
  requiresResearch: boolean;
  involvesMultipleSources: boolean;
  needsComparison: boolean;
  strategicAdvice: boolean;
  multiJurisdictional: boolean;
  documentAnalysis: boolean;
  conflictingLaw: boolean;
}

/**
 * Analyze query text and classify complexity using heuristics
 * This is a fast, local classification that doesn't require an API call
 */
export function classifyQueryComplexity(query: string): QueryComplexity {
  const lowerQuery = query.toLowerCase();
  const indicators: ComplexityIndicators = {
    multipleQuestions: (query.match(/\?/g) || []).length > 1,
    requiresResearch: /research|analyze|compare|evaluate|assess|review/.test(lowerQuery),
    involvesMultipleSources: /and|also|additionally|furthermore|multiple/.test(lowerQuery),
    needsComparison: /compare|versus|vs|difference between|contrast/.test(lowerQuery),
    strategicAdvice: /should i|what if|strategy|recommend|advise|best approach/.test(lowerQuery),
    multiJurisdictional: /jurisdiction|singapore and|cross-border|international/.test(lowerQuery),
    documentAnalysis: /contract|agreement|clause|document|draft/.test(lowerQuery) && query.length > 200,
    conflictingLaw: /conflict|inconsistent|unclear|ambiguous|disputed/.test(lowerQuery),
  };

  // Count complexity indicators
  const score = Object.values(indicators).filter(Boolean).length;

  // Check for simple query patterns
  const simplePatterns = [
    /^what is/i,
    /^define/i,
    /^when (is|was|does)/i,
    /^who (is|can)/i,
    /^how long/i,
    /limitation period/i,
  ];

  const isSimplePattern = simplePatterns.some(pattern => pattern.test(query));

  // Query length considerations
  const wordCount = query.split(/\s+/).length;

  // Classification logic
  if (isSimplePattern && wordCount < 15 && score === 0) {
    return 'simple';
  }

  if (indicators.multiJurisdictional || indicators.conflictingLaw || score >= 5) {
    return 'expert';
  }

  if (indicators.strategicAdvice || indicators.needsComparison || score >= 3) {
    return 'complex';
  }

  if (indicators.requiresResearch || indicators.documentAnalysis || score >= 1) {
    return 'moderate';
  }

  // Default to moderate for medium-length queries
  if (wordCount > 20) {
    return 'moderate';
  }

  return 'simple';
}

/**
 * Map query complexity to reasoning depth
 */
export function complexityToReasoningDepth(complexity: QueryComplexity): ReasoningDepth {
  const mapping: Record<QueryComplexity, ReasoningDepth> = {
    simple: 'quick',
    moderate: 'standard',
    complex: 'deep',
    expert: 'expert',
  };

  return mapping[complexity];
}

/**
 * Get recommended token budget based on complexity
 */
export function getTokenBudget(complexity: QueryComplexity): number {
  const budgets: Record<QueryComplexity, number> = {
    simple: 1024,
    moderate: 2048,
    complex: 4096,
    expert: 8192,
  };

  return budgets[complexity];
}

/**
 * Determine if multi-stage reasoning should be used
 */
export function shouldUseMultiStage(complexity: QueryComplexity): boolean {
  return complexity === 'complex' || complexity === 'expert';
}

/**
 * Determine if ReAct pattern should be used
 */
export function shouldUseReAct(complexity: QueryComplexity): boolean {
  return complexity === 'expert';
}

/**
 * Get temperature setting based on complexity
 * More complex queries benefit from slightly higher temperature for creativity
 */
export function getTemperatureForComplexity(complexity: QueryComplexity): number {
  const temperatures: Record<QueryComplexity, number> = {
    simple: 0.3,    // Low temperature for factual answers
    moderate: 0.5,  // Moderate temperature
    complex: 0.7,   // Higher for nuanced analysis
    expert: 0.7,    // Balanced for strategic reasoning
  };

  return temperatures[complexity];
}

/**
 * Comprehensive query analysis result
 */
export interface QueryAnalysis {
  complexity: QueryComplexity;
  reasoningDepth: ReasoningDepth;
  tokenBudget: number;
  temperature: number;
  useMultiStage: boolean;
  useReAct: boolean;
  reasoning: string;
}

/**
 * Perform comprehensive query analysis
 */
export function analyzeQuery(query: string): QueryAnalysis {
  const complexity = classifyQueryComplexity(query);
  const reasoningDepth = complexityToReasoningDepth(complexity);
  const tokenBudget = getTokenBudget(complexity);
  const temperature = getTemperatureForComplexity(complexity);
  const useMultiStage = shouldUseMultiStage(complexity);
  const useReAct = shouldUseReAct(complexity);

  // Generate reasoning explanation
  const reasoning = generateReasoningExplanation(complexity, query);

  return {
    complexity,
    reasoningDepth,
    tokenBudget,
    temperature,
    useMultiStage,
    useReAct,
    reasoning,
  };
}

/**
 * Generate human-readable explanation of complexity classification
 */
function generateReasoningExplanation(complexity: QueryComplexity, query: string): string {
  const explanations: Record<QueryComplexity, string> = {
    simple: 'Straightforward factual query requiring direct answer',
    moderate: 'Standard legal query requiring analysis of statutes or cases',
    complex: 'Multi-faceted query requiring deep analysis across multiple sources',
    expert: 'Expert-level query requiring comprehensive analysis, strategic thinking, or multi-jurisdictional consideration',
  };

  return explanations[complexity];
}

/**
 * Override complexity manually (for user control)
 */
export function overrideComplexity(
  analysis: QueryAnalysis,
  newDepth: ReasoningDepth
): QueryAnalysis {
  const complexityMap: Record<ReasoningDepth, QueryComplexity> = {
    quick: 'simple',
    standard: 'moderate',
    deep: 'complex',
    expert: 'expert',
  };

  const newComplexity = complexityMap[newDepth];

  return {
    ...analysis,
    complexity: newComplexity,
    reasoningDepth: newDepth,
    tokenBudget: getTokenBudget(newComplexity),
    temperature: getTemperatureForComplexity(newComplexity),
    useMultiStage: shouldUseMultiStage(newComplexity),
    useReAct: shouldUseReAct(newComplexity),
  };
}
