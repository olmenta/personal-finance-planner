"use client";

import React from "react";
import { Icon } from "@/components/ui/Icon";

/* The coach's header. The scripted conversation that used to live here was
   replaced by the real proposals feed (components/coach/CoachFeed.tsx);
   free-form chat comes later. */

export function CoachHeader({ note = "Watching your money" }: { note?: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: 20,
        borderBottom: "1px solid var(--border-hairline)",
      }}
    >
      <span
        style={{
          width: 40,
          height: 40,
          borderRadius: 999,
          background: "var(--grad-coach)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flex: "none",
        }}
      >
        <Icon name="sparkles" size={19} color="var(--mint-400)" />
      </span>
      <div style={{ flex: 1 }}>
        <div
          style={{
            font: "700 16px var(--font-sans)",
            letterSpacing: "-0.3px",
            color: "var(--text-strong)",
          }}
        >
          Coach
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            font: "500 12px var(--font-sans)",
            color: "var(--mint-600)",
          }}
        >
          <span style={{ width: 7, height: 7, borderRadius: 999, background: "var(--mint-500)" }} />{" "}
          {note}
        </div>
      </div>
    </div>
  );
}
