import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyFetch(`/categories/${id}`, {
    method: "PATCH",
    body: await request.text(),
  });
}
