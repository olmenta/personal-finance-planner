import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { search } = new URL(request.url);
  return proxyFetch(`/transactions${search}`);
}

export async function POST(request: Request) {
  return proxyFetch("/transactions", {
    method: "POST",
    body: await request.text(),
  });
}
