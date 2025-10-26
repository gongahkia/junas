import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { validateData } from '@/lib/validation';
import { formatErrorResponse } from '@/lib/api-utils';

/**
 * Validation middleware for API routes
 */

type Handler = (request: NextRequest, validatedData: any) => Promise<NextResponse>;

/**
 * Wrap an API route handler with validation middleware
 */
export function withValidation<T extends z.ZodSchema>(
  schema: T,
  handler: Handler
) {
  return async (request: NextRequest): Promise<NextResponse> => {
    try {
      // Parse request body
      const body = await request.json();

      // Validate using schema
      const validation = validateData(schema, body);

      if (!validation.success) {
        return NextResponse.json(
          { error: validation.error, success: false },
          { status: 400 }
        );
      }

      // Call the actual handler with validated data
      return await handler(request, validation.data);
    } catch (error: any) {
      if (error.message?.includes('JSON')) {
        return NextResponse.json(
          { error: 'Invalid JSON in request body', success: false },
          { status: 400 }
        );
      }

      return NextResponse.json(
        formatErrorResponse(error, 'Request processing'),
        { status: 500 }
      );
    }
  };
}

/**
 * Rate limiting state (simple in-memory implementation)
 * In production, use Redis or similar
 */
const requestCounts = new Map<string, { count: number; resetAt: number }>();

/**
 * Simple rate limiting middleware
 */
export function withRateLimit(
  maxRequests: number = 100,
  windowMs: number = 60000 // 1 minute
) {
  return (handler: (request: NextRequest) => Promise<NextResponse>) => {
    return async (request: NextRequest): Promise<NextResponse> => {
      // Get client identifier (IP or session)
      const clientId = request.headers.get('x-forwarded-for') || 'anonymous';
      const now = Date.now();

      // Get or create rate limit entry
      let entry = requestCounts.get(clientId);

      if (!entry || now > entry.resetAt) {
        // Reset or create new entry
        entry = { count: 1, resetAt: now + windowMs };
        requestCounts.set(clientId, entry);
      } else {
        entry.count++;
      }

      // Check if limit exceeded
      if (entry.count > maxRequests) {
        const retryAfter = Math.ceil((entry.resetAt - now) / 1000);
        return NextResponse.json(
          {
            error: 'Rate limit exceeded. Please try again later.',
            code: 'RATE_LIMIT_EXCEEDED',
            retryAfter,
            success: false,
          },
          {
            status: 429,
            headers: {
              'Retry-After': retryAfter.toString(),
              'X-RateLimit-Limit': maxRequests.toString(),
              'X-RateLimit-Remaining': Math.max(0, maxRequests - entry.count).toString(),
              'X-RateLimit-Reset': new Date(entry.resetAt).toISOString(),
            },
          }
        );
      }

      // Call handler
      const response = await handler(request);

      // Add rate limit headers to successful responses
      response.headers.set('X-RateLimit-Limit', maxRequests.toString());
      response.headers.set('X-RateLimit-Remaining', Math.max(0, maxRequests - entry.count).toString());
      response.headers.set('X-RateLimit-Reset', new Date(entry.resetAt).toISOString());

      return response;
    };
  };
}

/**
 * Clean up expired rate limit entries periodically
 */
setInterval(() => {
  const now = Date.now();
  for (const [clientId, entry] of requestCounts.entries()) {
    if (now > entry.resetAt) {
      requestCounts.delete(clientId);
    }
  }
}, 60000); // Clean up every minute
