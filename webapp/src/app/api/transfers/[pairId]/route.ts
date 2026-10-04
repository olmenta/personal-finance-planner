import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ pairId: string }> };

export async function GET(_request: Request, { params }: Params) {
  const { pairId } = await params;
  return proxyFetch(`/transfers/${pairId}`);
}

export async function PATCH(request: Request, { params }: Params) {
  const { pairId } = await params;
  return proxyFetch(`/transfers/${pairId}`, {
    method: "PATCH",
    body: await request.text(),
  });
}

export async function DELETE(_request: Request, { params }: Params) {
  const { pairId } = await params;
  return proxyFetch(`/transfers/${pairId}`, { method: "DELETE" });
}
