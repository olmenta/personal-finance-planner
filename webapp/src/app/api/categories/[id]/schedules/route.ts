import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function GET(_request: Request, { params }: Params) {
  const { id } = await params;
  return proxyFetch(`/categories/${id}/schedules`);
}

export async function POST(request: Request, { params }: Params) {
  const { id } = await params;
  return proxyFetch(`/categories/${id}/schedules`, {
    method: "POST",
    body: await request.text(),
  });
}
