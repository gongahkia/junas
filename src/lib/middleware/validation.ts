import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { validateData } from '@/lib/validation';
import { formatErrorResponse } from '@/lib/api-utils';

/**
 * Validation middleware for API routes
 */

type Handler<T> = (request: NextRequest, validatedData: T) => Promise<NextResponse>;

/**
 * Wrap an API route handler with validation middleware
 */
export function withValidation<T extends z.ZodSchema>(
  schema: T,
  handler: Handler<z.infer<T>>
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
      return await handler(request, validation.data as z.infer<T>);
    } catch (error: unknown) {
      // Handle known error patterns safely
      const errorMessage = error instanceof Error ? error.message : String(error);

      if (errorMessage.includes('JSON')) {
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
 * Rate limiting with Upstash Redis (production-ready)
 * Falls back to in-memory if Upstash is not configured
 */

// In-memory fallback for development
const requestCounts = new Map<string, { count: number; resetAt: number }>();

// Lazy-load Upstash to avoid errors if not configured
let rateLimiter: any = null;

async function getRateLimiter() {
  if (rateLimiter) return rateLimiter;

  // Check if Upstash is configured
  const upstashUrl = process.env.UPSTASH_REDIS_REST_URL;
  const upstashToken = process.env.UPSTASH_REDIS_REST_TOKEN;

  if (upstashUrl && upstashToken) {
    try {
      const { Ratelimit } = await import('@upstash/ratelimit');
      const { Redis } = await import('@upstash/redis');

      const redis = new Redis({
        url: upstashUrl,
        token: upstashToken,
      });

      rateLimiter = new Ratelimit({
        redis,
        limiter: Ratelimit.slidingWindow(100, '60 s'),
        analytics: true,
        prefix: 'junas:ratelimit',
      });

      return rateLimiter;
    } catch (error) {
      console.error('[RateLimit] Failed to initialize Upstash, falling back to in-memory:', error);
      return null;
    }
  }

  return null;
}

/**
 * Rate limiting middleware with Upstash support
 */
export function withRateLimit(
  maxRequests: number = 100,
  windowMs: number = 60000 // 1 minute
) {
  return (handler: (request: NextRequest) => Promise<NextResponse>) => {
    return async (request: NextRequest): Promise<NextResponse> => {
      // Get client identifier (IP or session)
      const clientId = request.headers.get('x-forwarded-for') ||
        request.headers.get('x-real-ip') ||
        'anonymous';

      const limiter = await getRateLimiter();

      if (limiter) {
        // Use Upstash rate limiting
        try {
          const { success, limit, remaining, reset } = await limiter.limit(clientId);

          if (!success) {
            const resetDate = new Date(reset);
            const retryAfter = Math.ceil((reset - Date.now()) / 1000);

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
                  'X-RateLimit-Limit': limit.toString(),
                  'X-RateLimit-Remaining': remaining.toString(),
                  'X-RateLimit-Reset': resetDate.toISOString(),
                },
              }
            );
          }

          // Call handler and add rate limit headers
          const response = await handler(request);
          response.headers.set('X-RateLimit-Limit', limit.toString());
          response.headers.set('X-RateLimit-Remaining', remaining.toString());
          response.headers.set('X-RateLimit-Reset', new Date(reset).toISOString());

          return response;
        } catch (error) {
          console.error('[RateLimit] Upstash error, proceeding without rate limit:', error);
          // Fallback: allow request if Upstash fails
          return await handler(request);
        }
      } else {
        // Fallback to in-memory rate limiting
        const now = Date.now();
        let entry = requestCounts.get(clientId);

        if (!entry || now > entry.resetAt) {
          entry = { count: 1, resetAt: now + windowMs };
          requestCounts.set(clientId, entry);
        } else {
          entry.count++;
        }

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

        const response = await handler(request);
        response.headers.set('X-RateLimit-Limit', maxRequests.toString());
        response.headers.set('X-RateLimit-Remaining', Math.max(0, maxRequests - entry.count).toString());
        response.headers.set('X-RateLimit-Reset', new Date(entry.resetAt).toISOString());

        return response;
      }
    };
  };
}

/**
 * Clean up expired in-memory rate limit entries periodically
 */
if (typeof global !== 'undefined') {
  setInterval(() => {
    const now = Date.now();
    for (const [clientId, entry] of requestCounts.entries()) {
      if (now > entry.resetAt) {
        requestCounts.delete(clientId);
      }
    }
  }, 60000); // Clean up every minute
}
