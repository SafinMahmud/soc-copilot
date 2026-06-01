import { NextRequest, NextResponse } from "next/server";

// Cloud Run timeout is configured separately; this helps on Vercel-like hosts.
export const maxDuration = 900;

function backendBaseUrl(): string {
  return (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8001"
  ).replace(/\/$/, "");
}

async function proxy(request: NextRequest, path: string[]) {
  const segment = path.join("/");
  const target = `${backendBaseUrl()}/api/${segment}${request.nextUrl.search}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  const upstream = await fetch(target, {
    ...init,
    signal: AbortSignal.timeout(15 * 60 * 1000),
  });
  const body = await upstream.text();

  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "content-type":
        upstream.headers.get("content-type") || "application/json",
    },
  });
}

export async function GET(
  request: NextRequest,
  context: { params: { path: string[] } }
) {
  return proxy(request, context.params.path);
}

export async function POST(
  request: NextRequest,
  context: { params: { path: string[] } }
) {
  return proxy(request, context.params.path);
}
