import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import createCsrfProtect from 'edge-csrf';

// Initialize CSRF protection
const csrfProtect = createCsrfProtect({
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
  },
  ignoreMethods: ['GET', 'HEAD', 'OPTIONS'],
});

export async function middleware(request: NextRequest) {
  const response = NextResponse.next();

  // Skip CSRF for specific paths
  if (request.nextUrl.pathname === '/api/auth/keys') {
    return response;
  }

  // Apply CSRF protection
  try {
    await csrfProtect(request, response);
  } catch (err) {
    if (err instanceof Error && err.message === 'invalid csrf token') {
      return new NextResponse('Invalid CSRF Token', { status: 403 });
    }
    throw err;
  }

  // Set the CSRF token in a custom header for the client to read if needed
  // Note: edge-csrf sets a Set-Cookie header on the response automatically.

  return response;
}

export const config = {
  matcher: ['/api/:path*'],
};
