import { proxyFetch } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

export async function POST() {
  return proxyFetch("/onboarding/template", { method: "POST" });
}
