"use client";

import { usePathname } from "next/navigation";
import { CoachFeed } from "@/components/coach/CoachFeed";
import { CoachHeader } from "./CoachConversation";

/* Persistent Coach rail on the right of the dashboard (≥1440px). */
export function CoachRail() {
  // The /coach page shows the same feed full width: no second copy beside it.
  if (usePathname() === "/coach") return null;
  return (
    <aside
      className="app-coach-rail"
      style={{
        width: 360,
        flex: "none",
        background: "var(--surface)",
        borderLeft: "1px solid var(--border-hairline)",
        flexDirection: "column",
        height: "100%",
      }}
    >
      <CoachHeader />
      <CoachFeed />
    </aside>
  );
}
