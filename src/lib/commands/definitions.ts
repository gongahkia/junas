
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
