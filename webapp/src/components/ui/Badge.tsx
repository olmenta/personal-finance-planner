import React from "react";
import { Icon } from "./Icon";

export type BadgeTone =
  | "brand"
  | "mint"
  | "income"
  | "expense"
  | "info"
  | "warning"
  | "neutral"
  | "dark";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  solid?: boolean;
  icon?: string;
  dot?: boolean;
}

const map: Record<
  BadgeTone,
  { soft: [string, string]; solid: [string, string]; dotc: string }
> = {
  brand: { soft: ["var(--violet-100)", "var(--violet-700)"], solid: ["var(--brand)", "#fff"], dotc: "var(--brand)" },
  mint: { soft: ["var(--mint-100)", "var(--mint-700)"], solid: ["var(--accent)", "#fff"], dotc: "var(--accent)" },
  income: { soft: ["var(--income-soft)", "#0E8B5A"], solid: ["var(--income)", "#fff"], dotc: "var(--income)" },
  expense: { soft: ["var(--expense-soft)", "#C42E1E"], solid: ["var(--expense)", "#fff"], dotc: "var(--expense)" },
  info: { soft: ["var(--info-soft)", "#1E6FA8"], solid: ["var(--info)", "#fff"], dotc: "var(--info)" },
  warning: { soft: ["var(--warning-soft)", "#A66A0A"], solid: ["var(--warning)", "#fff"], dotc: "var(--warning)" },
  neutral: { soft: ["var(--gray-100)", "var(--ink-700)"], solid: ["var(--ink-900)", "#fff"], dotc: "var(--gray-400)" },
  dark: { soft: ["var(--ink-900)", "#fff"], solid: ["var(--ink-900)", "#fff"], dotc: "#fff" },
};

export function Badge({
  children,
  tone = "neutral",
  solid = false,
  icon,
  dot = false,
  style,
  ...rest
}: BadgeProps) {
  const t = map[tone];
  const [bg, fg] = solid ? t.solid : t.soft;

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        background: bg,
        color: fg,
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        fontSize: 12,
        lineHeight: 1,
        letterSpacing: "0.1px",
        padding: "5px 10px",
        borderRadius: "var(--r-full)",
        whiteSpace: "nowrap",
        ...style,
      }}
      {...rest}
    >
      {dot && (
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: t.dotc,
            flex: "none",
          }}
        />
      )}
      {icon && <Icon name={icon} size={13} strokeWidth={2.5} />}
      {children}
    </span>
  );
}
