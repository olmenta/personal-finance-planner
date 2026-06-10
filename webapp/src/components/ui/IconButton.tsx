"use client";

import React from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/shadcn/tooltip";
import { Icon } from "./Icon";

type IconButtonVariant = "soft" | "ghost" | "plain" | "dark" | "fab";
type IconButtonSize = "sm" | "md" | "lg";

export interface IconButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: string;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
  round?: boolean;
  ariaLabel?: string;
  tooltip?: string;
}

const sizes: Record<IconButtonSize | "fab", number> = { sm: 34, md: 42, lg: 50, fab: 60 };
const iconSizes: Record<IconButtonSize | "fab", number> = { sm: 18, md: 20, lg: 22, fab: 26 };

const variants: Record<IconButtonVariant, React.CSSProperties> = {
  soft: {
    background: "var(--brand-soft)",
    color: "var(--violet-700)",
    border: "1px solid transparent",
    boxShadow: "none",
  },
  ghost: {
    background: "var(--surface)",
    color: "var(--text-body)",
    border: "1px solid var(--border-hairline)",
    boxShadow: "var(--shadow-xs)",
  },
  plain: {
    background: "transparent",
    color: "var(--text-body)",
    border: "1px solid transparent",
    boxShadow: "none",
  },
  dark: {
    background: "var(--ink-900)",
    color: "#fff",
    border: "1px solid transparent",
    boxShadow: "var(--shadow-md)",
  },
  /* The FAB is the only surface that carries the violet glow shadow. */
  fab: {
    background: "var(--brand)",
    color: "#fff",
    border: "1px solid transparent",
    boxShadow: "var(--shadow-fab)",
  },
};

export function IconButton({
  icon,
  variant = "ghost",
  size = "md",
  round = true,
  disabled = false,
  ariaLabel,
  tooltip,
  style,
  ...rest
}: IconButtonProps) {
  const isFab = variant === "fab";
  const d = isFab ? sizes.fab : sizes[size];
  const v = variants[variant];

  const btn = (
    <button
      type="button"
      aria-label={ariaLabel}
      disabled={disabled}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: d,
        height: d,
        flex: "none",
        borderRadius: round ? "var(--r-full)" : "var(--r-md)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.45 : 1,
        transition:
          "transform var(--dur-fast) var(--ease-spring), background var(--dur-base) var(--ease-out)",
        ...v,
        ...style,
      }}
      onMouseDown={(e) => {
        if (!disabled) e.currentTarget.style.transform = "scale(0.94)";
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.transform = "scale(1)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "scale(1)";
      }}
      {...rest}
    >
      <Icon
        name={icon}
        size={isFab ? iconSizes.fab : iconSizes[size]}
        strokeWidth={2.25}
      />
    </button>
  );

  const label = tooltip ?? ariaLabel;
  if (!label) return btn;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{btn}</TooltipTrigger>
      <TooltipContent side="bottom" style={{ borderRadius: "var(--r-xs)" }}>
        {label}
      </TooltipContent>
    </Tooltip>
  );
}
