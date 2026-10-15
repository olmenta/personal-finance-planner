import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { search } = new URL(request.url);
  return proxyFetch(`/coach/actions${search}`);
}

export async function POST(request: Request) {
  return proxyFetch("/coach/actions", { method: "POST", body: await request.text() });
}
