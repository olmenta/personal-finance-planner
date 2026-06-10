import React from "react";
import { Icon } from "./Icon";

export type ChipTone =
  | "violet"
  | "mint"
  | "income"
  | "expense"
  | "info"
  | "warning"
  | "neutral";

const TONES: Record<ChipTone, [string, string]> = {
  violet: ["var(--violet-100)", "var(--violet-600)"],
  mint: ["var(--mint-100)", "var(--mint-600)"],
  income: ["var(--income-soft)", "var(--income)"],
  expense: ["var(--expense-soft)", "var(--expense)"],
  info: ["var(--info-soft)", "var(--info)"],
  warning: ["var(--warning-soft)", "var(--warning)"],
  neutral: ["var(--gray-100)", "var(--ink-700)"],
};

export interface IconChipProps {
  icon: string;
  tone?: ChipTone;
  size?: number;
  shape?: "rounded" | "circle";
  style?: React.CSSProperties;
}

/* Category icon chip: a soft tinted square holding a full-color glyph.
   The transaction's category decides the tone. */
export function IconChip({
  icon,
  tone = "neutral",
  size = 46,
  shape = "rounded",
  style,
}: IconChipProps) {
  const [bg, fg] = TONES[tone] || TONES.neutral;
  return (
    <span
      style={{
        width: size,
        height: size,
        flex: "none",
        borderRadius: shape === "circle" ? "var(--r-full)" : "var(--r-md)",
        background: bg,
        color: fg,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        ...style,
      }}
    >
      <Icon name={icon} size={size * 0.46} strokeWidth={2.25} />
    </span>
  );
}
