import { getIronSession, SessionOptions } from 'iron-session';
import { cookies } from 'next/headers';

export interface SessionData {
  apiKeys?: {
    gemini?: string;
    openai?: string;
    claude?: string;
    ollama?: string;
    lmstudio?: string;
  };
  createdAt?: number;
}

export const sessionOptions: SessionOptions = {
  password: process.env.SESSION_SECRET || 'default_secret_at_least_32_chars_long',
  cookieName: 'junas_session',
  cookieOptions: {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 7, // 1 week
    path: '/',
  },
};

export async function getSession() {
  const cookieStore = await cookies();
  return getIronSession<SessionData>(cookieStore, sessionOptions);
}
