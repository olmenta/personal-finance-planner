/* BFF → FastAPI proxy helper (server-only). The browser never talks to the
   Python API directly; Route Handlers call this and pass bodies/statuses
   through unchanged (spec: bff-proxy). */

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function proxyFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    return Response.json({ code: "backend_unavailable" }, { status: 502 });
  }

  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
