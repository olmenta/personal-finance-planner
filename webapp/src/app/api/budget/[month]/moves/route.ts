import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ month: string }> },
) {
  const { month } = await params;
  return proxyFetch(`/budget/${month}/moves`, {
    method: "POST",
    body: await request.text(),
  });
}
