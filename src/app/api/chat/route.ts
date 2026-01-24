import { NextRequest, NextResponse } from 'next/server';
import { ProviderFactory } from '@/lib/ai/provider-factory';
import { withValidation } from '@/lib/middleware/validation';
import { ChatRequestSchema } from '@/lib/validation';

export const POST = withValidation(ChatRequestSchema, async (request, body) => {
  try {
    const { messages, provider, apiKey, tools, options } = body;

    // Create provider instance
    const providerInstance = await ProviderFactory.createProvider((provider || 'gemini') as any, {
      // Default to gemini if undefined (schema allows optional?) - Validation schema says provider is NOT in schema?
      // check schema: model, temperature etc are there. messages is there. provider/apiKey are NOT in ChatRequestSchema?
      // Let's check schema content again.
      // ChatRequestSchema: messages, model, temperature, maxTokens, stream.
      // Body has: messages, provider, apiKey, tools, options.
      // Schema needs updating or we only validate partial.
      // Wait, ChatRequestSchema definition from previous view_file:
      // export const ChatRequestSchema = z.object({
      //   messages: z.array(MessageSchema).min(1, 'At least one message is required'),
      //   model: z.string().optional(),
      //   temperature: z.number().min(0).max(2).optional(),
      //   maxTokens: z.number().min(1).max(100000).optional(),
      //   stream: z.boolean().optional(),
      // });
      // It MISSES 'provider', 'apiKey', 'tools'.
      // If I use withValidation, it passes 'validatedData' which only contains schema fields if strict.
      // zod.parse strips unknown keys by default? No, .parse passes them through unless .strict() is used? z.object() strips unknown by default.
      // So 'provider' and 'apiKey' will be LOST if I use this schema as is.

      // I must UPDATE the schema first or UPDATE the route to use a better schema.
      // I will update the schema in a separate step or just define it here.
      // Better to update validation.ts.

      // ABORTING this tool call to fix schema first.
      name: provider || 'gemini',
      displayName: provider || 'Gemini',
      apiKey: apiKey || '',
      model: options?.model || 'default',
      temperature: options?.temperature || 0.7,
      maxTokens: options?.maxTokens || 4000,
      enabled: true,
    });

    // Generate response
    const response = await providerInstance.generateResponse(messages, tools, options);

    return NextResponse.json({
      content: response.content,
      usage: response.usage,
      model: response.model,
      finishReason: response.finishReason,
    });
  } catch (error: any) {
    console.error('Chat API error:', error);

    return NextResponse.json(
      {
        error: error.message || 'An error occurred while processing your request',
        code: error.code || 'UNKNOWN_ERROR',
        retryable: error.retryable || false,
      },
      { status: 500 }
    );
  }
});

export async function GET() {
  return NextResponse.json({
    message: 'Chat API endpoint',
    supportedProviders: ProviderFactory.getAvailableProviders(),
  });
}
