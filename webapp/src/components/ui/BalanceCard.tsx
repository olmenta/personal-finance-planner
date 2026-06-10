import React from "react";

export interface BalanceCardProps {
  label?: string;
  amount: string;
  cents?: string;
  delta?: React.ReactNode;
  align?: "center" | "left";
  style?: React.CSSProperties;
  children?: React.ReactNode;
}

/* Hero balance card — violet gradient, amount with dimmed cents, and a
   translucent delta pill. The defining surface of the Olmenta home. */
export function BalanceCard({
  label = "Current balance",
  amount,
  cents,
  delta,
  align = "center",
  style,
  children,
}: BalanceCardProps) {
  return (
    <div
      style={{
        background: "var(--grad-balance)",
        borderRadius: "var(--r-2xl)",
        padding: "30px 28px 32px",
        color: "#fff",
        textAlign: align,
        position: "relative",
        overflow: "hidden",
        boxShadow: "0 18px 40px rgba(106,71,234,.32)",
        ...style,
      }}
    >
      <div
        style={{
          font: "500 14px var(--font-sans)",
          opacity: 0.85,
          letterSpacing: "0.1px",
        }}
      >
        {label}
      </div>
      <div
        style={{
          font: "800 44px var(--font-sans)",
          letterSpacing: "-1.6px",
          lineHeight: 1.05,
          margin: "8px 0 14px",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {amount}
        {cents && <span style={{ opacity: 0.55 }}>{cents}</span>}
      </div>
      {delta && (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: "rgba(255,255,255,.18)",
            color: "#fff",
            backdropFilter: "blur(6px)",
            padding: "7px 14px",
            borderRadius: "var(--r-full)",
            font: "600 13px var(--font-sans)",
          }}
        >
          {delta}
        </span>
      )}
      {children}
    </div>
  );
}
