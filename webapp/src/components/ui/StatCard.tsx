import React from "react";
import { Icon } from "./Icon";
import { IconChip, type ChipTone } from "./IconChip";

export interface StatCardProps {
  icon: string;
  tone?: ChipTone;
  label: string;
  value: string;
  info?: boolean;
  style?: React.CSSProperties;
}

/* Compact metric card — icon chip, label with info affordance, and a tabular
   value. Used in the "Your money" income/expense pair. */
export function StatCard({
  icon,
  tone = "income",
  label,
  value,
  info = true,
  style,
}: StatCardProps) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border-hairline)",
        borderRadius: "var(--r-xl)",
        padding: 18,
        boxShadow: "var(--shadow-sm)",
        ...style,
      }}
    >
      <IconChip icon={icon} tone={tone} size={44} />
      <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 14 }}>
        <span style={{ font: "500 13px var(--font-sans)", color: "var(--text-muted)" }}>
          {label}
        </span>
        {info && <Icon name="info" size={13} color="var(--text-subtle)" />}
      </div>
      <div
        style={{
          font: "700 22px var(--font-sans)",
          letterSpacing: "-0.5px",
          marginTop: 4,
          fontVariantNumeric: "tabular-nums",
          color: "var(--text-strong)",
        }}
      >
        {value}
      </div>
    </div>
  );
}
