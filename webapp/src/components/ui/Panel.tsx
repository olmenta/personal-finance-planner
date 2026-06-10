import React from "react";

export interface PanelProps {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

/* White content panel — the standard Olmenta card: 24px radius, hairline
   border and a soft shadow, both lightly. */
export function Panel({ title, action, children, style }: PanelProps) {
  return (
    <section
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border-hairline)",
        borderRadius: "var(--r-xl)",
        padding: 22,
        boxShadow: "var(--shadow-sm)",
        ...style,
      }}
    >
      {title && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 18,
          }}
        >
          <h2
            style={{
              font: "700 17px var(--font-sans)",
              letterSpacing: "-0.3px",
              color: "var(--text-strong)",
            }}
          >
            {title}
          </h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
