import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  return proxyFetch("/categories/groups", {
    method: "POST",
    body: await request.text(),
  });
}
