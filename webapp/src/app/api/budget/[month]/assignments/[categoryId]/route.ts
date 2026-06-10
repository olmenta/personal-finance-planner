import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ month: string; categoryId: string }> },
) {
  const { month, categoryId } = await params;
  return proxyFetch(`/budget/${month}/assignments/${categoryId}`, {
    method: "PUT",
    body: await request.text(),
  });
}
