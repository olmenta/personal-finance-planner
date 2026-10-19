/* BFF → FastAPI proxy helper (server-only). The browser never talks to the
   Python API directly; Route Handlers call this, which attaches the
   session's access token, and pass bodies/statuses through unchanged
   (spec: bff-proxy, authentication). */

import { auth0 } from "@/lib/auth0";

export const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

/** The session's access token for this environment's API, as a header —
    or a 401 response when there's no usable session (spec: authentication).
    The token never reaches the browser. */
export async function authHeaders(): Promise<Record<string, string> | Response> {
  if (!auth0) return {}; // local/test without Auth0: the development user
  try {
    const { token } = await auth0.getAccessToken();
    return { Authorization: `Bearer ${token}` };
  } catch {
    return Response.json({ code: "unauthenticated" }, { status: 401 });
  }
}

export async function proxyFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const auth = await authHeaders();
  if (auth instanceof Response) return auth;
  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers, ...auth },
      cache: "no-store",
    });
  } catch {
    return Response.json({ code: "backend_unavailable" }, { status: 502 });
  }

  // Null-body statuses (204/205/304) reject any body, even an empty string.
  if ([204, 205, 304].includes(upstream.status)) {
    return new Response(null, { status: upstream.status });
  }

  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
