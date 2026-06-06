import { NextResponse, type NextRequest } from "next/server";

const API_KEYS_ENV = "API_KEYS";
const API_KEY_HEADER = "X-API-Key";

function parseApiKeys(raw: string | undefined): string[] {
  const value = raw?.trim();
  if (!value) return [];
  if (value.startsWith("[")) {
    try {
      const loaded = JSON.parse(value);
      if (Array.isArray(loaded)) return loaded.map(String).map((item) => item.trim()).filter(Boolean);
    } catch {
      return [];
    }
  }
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function accessKeyRequired() {
  return new NextResponse(
    `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Access key required</title>
</head>
<body style="margin:0;font-family:system-ui,-apple-system,sans-serif;background:#fff;color:#0f172a;">
  <main style="max-width:680px;margin:0 auto;padding:2rem 1.25rem;">
    <a href="/" style="font-size:0.8rem;color:#64748b;text-decoration:none;">&larr; Back</a>
    <section style="margin-top:1rem;padding:1rem;border:1px solid #fecaca;border-radius:0.5rem;background:#fef2f2;color:#7f1d1d;">
      <h1 style="font-size:1.2rem;margin:0 0 0.5rem 0;font-weight:600;">This demo requires an access key.</h1>
      <p style="font-size:0.9rem;margin:0 0 0.5rem 0;color:#991b1b;">Set <code>API_KEYS</code> on the deployment, then send the shared secret in the <code>X-API-Key</code> header.</p>
      <p style="font-size:0.78rem;margin:0;color:#b91c1c;">Option A is the launch-day minimum. For the hosted demo, Vercel password protection is still recommended at the deploy edge.</p>
    </section>
  </main>
</body>
</html>`,
    {
      status: 401,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    },
  );
}

export function middleware(request: NextRequest) {
  const apiKey = request.headers.get(API_KEY_HEADER)?.trim();
  const apiKeys = parseApiKeys(process.env[API_KEYS_ENV]);
  if (!apiKey || !apiKeys.includes(apiKey)) return accessKeyRequired();
  return NextResponse.next();
}

export const config = {
  matcher: ["/benchmarks/:path*"],
};
