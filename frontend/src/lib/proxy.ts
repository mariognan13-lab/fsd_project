import { NextResponse } from "next/server";

const configuredBackendUrl = process.env.BACKEND_URL || "http://localhost:5050";
const BACKEND_URL = /^[a-z][a-z\d+.-]*:\/\//i.test(configuredBackendUrl)
  ? configuredBackendUrl
  : `https://${configuredBackendUrl}`;

// The backend allows slow upstreams up to OVERPASS_TIMEOUT_MS (45s),
// so the proxy allows ample time before timing out.
const BACKEND_TIMEOUT_MS = Number(process.env.BACKEND_TIMEOUT_MS || 90_000);

/**
 * Forward a request to the FastAPI backend, preserving the query string,
 * request body and method. Returns the backend JSON verbatim.
 */
export async function forward(
  req: Request,
  path: string,
  init: { method?: string; body?: BodyInit | null; timeoutMs?: number } = {}
): Promise<NextResponse> {
  const incoming = new URL(req.url);
  const target = new URL(path, BACKEND_URL);

  target.search = incoming.search;

  const timeoutMs = init.timeoutMs ?? BACKEND_TIMEOUT_MS;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(target, {
      method: init.method ?? req.method,
      headers: {
        accept: "application/json",
        "content-type": req.headers.get("content-type") ?? "application/json",
      },
      body: init.body ?? (init.method ? null : null),
      signal: controller.signal,
      cache: "no-store",
    });

    const text = await response.text();
    let payload: unknown;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = { error: { code: "BAD_GATEWAY", message: text || "Invalid backend response." } };
    }

    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    const isTimeout = controller.signal.aborted;
    const message = isTimeout
      ? `Backend request timed out after ${Math.round(timeoutMs / 1000)}s.`
      : error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      {
        error: {
          code: isTimeout ? "BACKEND_TIMEOUT" : "BACKEND_UNREACHABLE",
          message: `Could not reach backend: ${message}`,
        },
      },
      { status: isTimeout ? 504 : 502 }
    );
  } finally {
    clearTimeout(timeout);
  }
}

