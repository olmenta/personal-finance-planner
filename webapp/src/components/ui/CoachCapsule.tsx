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
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        background: "var(--grad-coach)",
        color: "#fff",
        borderRadius: "var(--r-full)",
        padding: "12px 16px 12px 14px",
        boxShadow: "var(--shadow-coach)",
        cursor: onClick ? "pointer" : "default",
        ...style,
      }}
    >
      <span style={{ display: "flex", alignItems: "center", gap: 11, minWidth: 0 }}>
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
        <span
          style={{
            font: "600 14.5px var(--font-sans)",
            letterSpacing: "-0.1px",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
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
          }}
        >
          {cta}
          <Icon name="chevron-right" size={16} />
        </span>
      )}
    </div>
  );
}
