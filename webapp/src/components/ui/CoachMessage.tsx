import React from "react";
import { Icon } from "./Icon";

export interface CoachMessageProps {
  role?: "coach" | "user";
  children: React.ReactNode;
  style?: React.CSSProperties;
}

/* A chat bubble in the Coach conversation. `role="coach"` renders a left-side
   bubble led by a sparkle avatar; `role="user"` renders a right-aligned violet
   bubble. Coach bubbles can carry rich children (cards, lists). */
export function CoachMessage({ role = "coach", children, style }: CoachMessageProps) {
  const isCoach = role === "coach";
  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        alignItems: "flex-end",
        flexDirection: isCoach ? "row" : "row-reverse",
        ...style,
      }}
    >
      {isCoach && (
        <span
          style={{
            width: 30,
            height: 30,
            flex: "none",
            borderRadius: "var(--r-full)",
            background: "var(--grad-coach)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon name="sparkles" size={15} color="var(--mint-400)" strokeWidth={2} />
        </span>
      )}
      <div
        style={{
          maxWidth: "78%",
          padding: "12px 15px",
          borderRadius: isCoach ? "4px 18px 18px 18px" : "18px 18px 4px 18px",
          background: isCoach ? "var(--surface)" : "var(--brand)",
          color: isCoach ? "var(--text-body)" : "#fff",
          border: isCoach ? "1px solid var(--border-hairline)" : "none",
          boxShadow: isCoach ? "var(--shadow-xs)" : "0 6px 16px rgba(124,92,252,.24)",
          font: "500 15px/1.5 var(--font-sans)",
          letterSpacing: "-0.1px",
        }}
      >
        {children}
      </div>
    </div>
  );
}
