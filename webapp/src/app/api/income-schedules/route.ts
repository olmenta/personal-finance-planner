import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyFetch("/income-schedules");
}

export async function POST(request: Request) {
  return proxyFetch("/income-schedules", { method: "POST", body: await request.text() });
}
