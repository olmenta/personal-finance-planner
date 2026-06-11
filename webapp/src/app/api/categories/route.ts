import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyFetch("/categories");
}

export async function POST(request: Request) {
  return proxyFetch("/categories", {
    method: "POST",
    body: await request.text(),
  });
}
