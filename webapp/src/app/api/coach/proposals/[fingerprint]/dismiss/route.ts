import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ fingerprint: string }> };

export async function POST(request: Request, { params }: Params) {
  const { fingerprint } = await params;
  return proxyFetch(`/coach/proposals/${encodeURIComponent(fingerprint)}/dismiss`, {
    method: "POST",
    body: (await request.text()) || "{}",
  });
}
