"use client";

import React from "react";
import { Icon } from "./Icon";

type ButtonVariant = "primary" | "accent" | "secondary" | "ghost" | "dark";
type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  iconLeft?: string;
  iconRight?: string;
  block?: boolean;
}

const sizes: Record<
  ButtonSize,
  { padding: string; fontSize: number; gap: number; icon: number }
> = {
  sm: { padding: "8px 14px", fontSize: 13.5, gap: 6, icon: 16 },
  md: { padding: "11px 20px", fontSize: 15, gap: 8, icon: 18 },
  lg: { padding: "15px 26px", fontSize: 16.5, gap: 9, icon: 20 },
};

const variants: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    background: "var(--brand)",
    color: "#fff",
    border: "1px solid transparent",
    boxShadow: "0 6px 16px rgba(124,92,252,.28)",
  },
  accent: {
    background: "var(--accent)",
    color: "#fff",
    border: "1px solid transparent",
    boxShadow: "0 6px 16px rgba(22,199,154,.28)",
  },
  secondary: {
    background: "var(--brand-soft)",
    color: "var(--violet-700)",
    border: "1px solid transparent",
    boxShadow: "none",
  },
  ghost: {
    background: "var(--surface)",
    color: "var(--text-strong)",
    border: "1px solid var(--border-hairline)",
    boxShadow: "var(--shadow-xs)",
  },
  dark: {
    background: "var(--ink-900)",
    color: "#fff",
    border: "1px solid transparent",
    boxShadow: "var(--shadow-md)",
  },
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  iconLeft,
  iconRight,
  block = false,
  disabled = false,
  type = "button",
  style,
  ...rest
}: ButtonProps) {
  const s = sizes[size];
  const v = variants[variant];

  return (
    <button
      type={type}
      disabled={disabled}
      style={{
        display: block ? "flex" : "inline-flex",
        width: block ? "100%" : "auto",
        alignItems: "center",
        justifyContent: "center",
        gap: s.gap,
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        fontSize: s.fontSize,
        letterSpacing: "-0.1px",
        lineHeight: 1,
        padding: s.padding,
        borderRadius: "var(--r-full)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.45 : 1,
        transition:
          "transform var(--dur-fast) var(--ease-spring), background var(--dur-base) var(--ease-out), box-shadow var(--dur-base) var(--ease-out)",
        whiteSpace: "nowrap",
        ...v,
        ...style,
      }}
      onMouseDown={(e) => {
        if (!disabled) e.currentTarget.style.transform = "scale(0.97)";
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.transform = "scale(1)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "scale(1)";
      }}
      {...rest}
    >
      {iconLeft && <Icon name={iconLeft} size={s.icon} strokeWidth={2.25} />}
      {children}
      {iconRight && <Icon name={iconRight} size={s.icon} strokeWidth={2.25} />}
    </button>
  );
}
