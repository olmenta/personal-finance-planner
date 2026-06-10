import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ month: string }> },
) {
  const { month } = await params;
  return proxyFetch(`/summary/${month}`);
}
