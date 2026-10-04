import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ pairId: string }> },
) {
  const { pairId } = await params;
  return proxyFetch(`/transfers/${pairId}/unlink`, { method: "POST" });
}
