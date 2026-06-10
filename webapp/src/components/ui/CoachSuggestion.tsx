"use client";

import React from "react";
import { Icon } from "./Icon";

export interface Suggestion {
  label: string;
  icon?: string;
}

export interface CoachSuggestionProps {
  suggestions?: (Suggestion | string)[];
  onPick?: (label: string) => void;
  style?: React.CSSProperties;
}

/* Tappable suggestion chips that prompt the user with things to ask the coach.
   A wrapping row of ghost pills with a small leading glyph. */
export function CoachSuggestion({ suggestions = [], onPick, style }: CoachSuggestionProps) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, ...style }}>
      {suggestions.map((s, i) => {
        const label = typeof s === "string" ? s : s.label;
        const icon = typeof s === "string" ? "sparkles" : s.icon || "sparkles";
        return (
          <button
            key={i}
            type="button"
            onClick={() => onPick?.(label)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              background: "var(--surface)",
              border: "1px solid var(--border-hairline)",
              borderRadius: "var(--r-full)",
              padding: "9px 14px",
              font: "600 13.5px var(--font-sans)",
              color: "var(--text-body)",
              cursor: "pointer",
              letterSpacing: "-0.1px",
              transition:
                "background var(--dur-base) var(--ease-out), border-color var(--dur-base) var(--ease-out)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--violet-50)";
              e.currentTarget.style.borderColor = "var(--violet-200)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "var(--surface)";
              e.currentTarget.style.borderColor = "var(--border-hairline)";
            }}
          >
            <Icon name={icon} size={14} color="var(--violet-500)" strokeWidth={2.25} />
            {label}
          </button>
        );
      })}
    </div>
  );
}
