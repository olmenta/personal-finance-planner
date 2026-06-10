"use client";

import React from "react";
import { IconChip, type ChipTone } from "./IconChip";

export interface TransactionRowProps {
  icon: string;
  tone?: ChipTone;
  title: string;
  subtitle?: React.ReactNode;
  amount: string;
  direction?: "in" | "out" | "none";
  balance?: string;
  card?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
}

/* One transaction line: category chip, title + sub-line, and a tabular amount
   colored by direction (income green / expense red). */
export function TransactionRow({
  icon,
  tone = "neutral",
  title,
  subtitle,
  amount,
  direction = "out",
  balance,
  card = true,
  onClick,
  style,
}: TransactionRowProps) {
  const amtColor =
    direction === "in"
      ? "var(--income)"
      : direction === "out"
        ? "var(--expense)"
        : "var(--text-strong)";
  const sign = direction === "in" ? "+" : direction === "out" ? "-" : "";

  return (
    <div
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 13,
        background: card ? "var(--surface)" : "transparent",
        border: card ? "1px solid var(--border-hairline)" : "none",
        borderRadius: "var(--r-lg)",
        padding: card ? "13px 15px" : "10px 0",
        boxShadow: card ? "var(--shadow-xs)" : "none",
        cursor: onClick ? "pointer" : "default",
        ...style,
      }}
    >
      <IconChip icon={icon} tone={tone} size={44} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            font: "600 15.5px var(--font-sans)",
            color: "var(--text-strong)",
            letterSpacing: "-0.2px",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {title}
        </div>
        {subtitle && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              font: "500 12.5px var(--font-sans)",
              color: "var(--text-muted)",
              marginTop: 2,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
      <div style={{ textAlign: "right", flex: "none" }}>
        <div
          style={{
            font: "700 15px var(--font-sans)",
            color: amtColor,
            fontVariantNumeric: "tabular-nums",
            letterSpacing: "-0.2px",
          }}
        >
          {sign}
          {amount}
        </div>
        {balance && (
          <div
            style={{
              font: "500 12px var(--font-sans)",
              color: "var(--text-subtle)",
              marginTop: 2,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {balance}
          </div>
        )}
      </div>
    </div>
  );
}
