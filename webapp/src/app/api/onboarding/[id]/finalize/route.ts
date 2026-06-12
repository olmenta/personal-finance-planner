import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyFetch(`/onboarding/${id}/finalize`, {
    method: "POST",
    body: await request.text(),
  });
}
