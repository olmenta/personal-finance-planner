import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyFetch("/accounts");
}

export async function POST(request: Request) {
  return proxyFetch("/accounts", {
    method: "POST",
    body: await request.text(),
  });
}
