"use client";

import { CoachConversation, CoachHeader } from "./CoachConversation";

/* Persistent Coach rail on the right of the dashboard (≥1440px). */
export function CoachRail() {
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
      <CoachConversation />
    </aside>
  );
}
