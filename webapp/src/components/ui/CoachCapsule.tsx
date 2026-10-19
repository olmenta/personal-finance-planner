"use client";

import React from "react";
import { Icon } from "./Icon";

export interface CoachCapsuleProps {
  message?: string;
  cta?: string;
  onClick?: () => void;
  accent?: "mint" | "violet";
  style?: React.CSSProperties;
}

/* The Coach capsule — Olmenta's signature dark "insight" banner. A sparkle
   glyph, a short message, and a trailing CTA. The only dark capsule surface
   in the product; it marks the AI coach's voice. */
export function CoachCapsule({
  message = "Your insight is ready",
  cta = "See it",
  onClick,
  accent = "mint",
  style,
}: CoachCapsuleProps) {
  const sparkColor = accent === "mint" ? "var(--mint-400)" : "var(--violet-300)";
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "8px 12px",
        background: "var(--grad-coach)",
        color: "#fff",
        // A pill on one line (54px tall); a rounded card when the CTA wraps.
        borderRadius: 27,
        padding: "12px 16px 12px 14px",
        boxShadow: "var(--shadow-coach)",
        cursor: onClick ? "pointer" : "default",
        ...style,
      }}
    >
      {/* When the message and the CTA don't fit on one line, the CTA moves
          under the message instead of squeezing it. */}
      <span style={{ display: "flex", alignItems: "center", gap: 11, minWidth: 0, flex: "1 1 220px" }}>
        <span
          style={{
            width: 30,
            height: 30,
            flex: "none",
            borderRadius: "var(--r-sm)",
            background: "rgba(255,255,255,.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon name="sparkles" size={16} color={sparkColor} strokeWidth={2} />
        </span>
        {/* At most two lines. */}
        <span
          data-testid="coach-capsule-message"
          style={{
            font: "600 14.5px/1.3 var(--font-sans)",
            letterSpacing: "-0.1px",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {message}
        </span>
      </span>
      {cta && (
        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: 3,
            font: "600 13.5px var(--font-sans)",
            color: "rgba(255,255,255,.85)",
            whiteSpace: "nowrap",
            flex: "none",
            marginLeft: "auto",
          }}
        >
          {cta}
          <Icon name="chevron-right" size={16} />
        </span>
      )}
    </div>
  );
}
