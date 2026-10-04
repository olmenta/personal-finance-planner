import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function PATCH(request: Request, { params }: Params) {
  const { id } = await params;
  return proxyFetch(`/schedules/${id}`, { method: "PATCH", body: await request.text() });
}

export async function DELETE(_request: Request, { params }: Params) {
  const { id } = await params;
  return proxyFetch(`/schedules/${id}`, { method: "DELETE" });
}
