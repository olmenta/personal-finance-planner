import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyFetch("/plan/income");
}

export async function PUT(request: Request) {
  return proxyFetch("/plan/income", { method: "PUT", body: await request.text() });
}
