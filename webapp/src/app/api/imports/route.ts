/* Multipart upload passthrough (design D7): proxyFetch's JSON Content-Type
   would break the multipart boundary, so this handler forwards the FormData
   and lets fetch set the header. */

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}/imports`, {
      method: "POST",
      body: await request.formData(),
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
