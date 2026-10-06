import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyFetch("/debts");
}

export async function POST(request: Request) {
  return proxyFetch("/debts", { method: "POST", body: await request.text() });
}
