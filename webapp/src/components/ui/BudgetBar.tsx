import React from "react";
import { IconChip, type ChipTone } from "./IconChip";

export interface BudgetBarProps {
  icon?: string;
  tone?: ChipTone;
  label: string;
  spent: string;
  limit?: string;
  percent?: number;
  style?: React.CSSProperties;
}

const FILLS: Partial<Record<ChipTone, string>> = {
  violet: "var(--violet-500)",
  mint: "var(--mint-500)",
  income: "var(--income)",
  warning: "var(--warning)",
  info: "var(--info)",
};

/* Budget / category progress bar. Shows spent vs limit with a tinted track;
   the fill turns expense-red once over 100%. Pass `percent` explicitly —
   formatted money strings aren't parsed. */
export function BudgetBar({
  icon,
  tone = "violet",
  label,
  spent,
  limit,
  percent = 0,
  style,
}: BudgetBarProps) {
  const over = percent > 100;
  const fillColor = over ? "var(--expense)" : FILLS[tone] || "var(--violet-500)";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 13, ...style }}>
      {icon && <IconChip icon={icon} tone={over ? "expense" : tone} size={40} />}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: 7,
          }}
        >
          <span
            style={{
              font: "600 14px var(--font-sans)",
              color: "var(--text-strong)",
              letterSpacing: "-0.1px",
            }}
          >
            {label}
          </span>
          <span
            style={{
              font: "600 13px var(--font-sans)",
              color: over ? "var(--expense)" : "var(--text-muted)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {spent}
            {limit ? (
              <span style={{ color: "var(--text-subtle)", fontWeight: 500 }}>
                {" "}
                / {limit}
              </span>
            ) : null}
          </span>
        </div>
        <div
          style={{
            height: 8,
            borderRadius: "var(--r-full)",
            background: "var(--gray-100)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${Math.min(percent, 100)}%`,
              height: "100%",
              borderRadius: "var(--r-full)",
              background: fillColor,
              transition: "width var(--dur-slow) var(--ease-out)",
            }}
          />
        </div>
      </div>
    </div>
  );
}
