import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { search } = new URL(request.url);
  return proxyFetch(`/plan/upcoming${search}`);
}
