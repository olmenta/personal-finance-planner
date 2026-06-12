import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  return proxyFetch("/transactions/apply-categories", {
    method: "POST",
    body: await request.text(),
  });
}
