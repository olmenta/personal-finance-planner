import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function PUT(request: Request) {
  return proxyFetch("/debts/extra", { method: "PUT", body: await request.text() });
}
