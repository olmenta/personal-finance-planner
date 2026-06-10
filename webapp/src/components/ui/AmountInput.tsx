"use client";

import React from "react";
import { money, parseEuroToCents } from "@/lib/format";

export interface AmountInputProps {
  valueCents: number;
  onCommit: (cents: number) => void;
  draft?: boolean;
  ariaLabel?: string;
  style?: React.CSSProperties;
}

/* Inline euro amount editor — right-aligned, tabular numerals, select-all on
   focus, commits on blur/Enter (es-ES parsing, comma decimals). Draft state
   gets the violet-tinted treatment until confirmed/edited. */
export function AmountInput({
  valueCents,
  onCommit,
  draft = false,
  ariaLabel,
  style,
}: AmountInputProps) {
  const [text, setText] = React.useState(money(valueCents / 100));
  const [focus, setFocus] = React.useState(false);

  React.useEffect(() => {
    if (!focus) setText(money(valueCents / 100));
  }, [valueCents, focus]);

  const commit = () => {
    const cents = parseEuroToCents(text);
    if (cents === null) {
      setText(money(valueCents / 100));
    } else if (cents !== valueCents) {
      onCommit(cents);
    } else {
      setText(money(valueCents / 100));
    }
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        background: draft ? "var(--violet-50)" : "var(--surface-sunk)",
        border: `1.5px solid ${focus ? "var(--brand)" : draft ? "var(--violet-200)" : "transparent"}`,
        borderRadius: "var(--r-sm)",
        padding: "0 10px",
        height: 36,
        boxShadow: focus ? "var(--focus-ring)" : "none",
        transition:
          "border-color var(--dur-base) var(--ease-out), box-shadow var(--dur-base) var(--ease-out)",
        ...style,
      }}
    >
      <input
        value={text}
        aria-label={ariaLabel}
        inputMode="decimal"
        onChange={(e) => setText(e.target.value)}
        onFocus={(e) => {
          setFocus(true);
          e.target.select();
        }}
        onBlur={() => {
          setFocus(false);
          commit();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
          if (e.key === "Escape") {
            setText(money(valueCents / 100));
            e.currentTarget.blur();
          }
        }}
        style={{
          width: 86,
          border: "none",
          outline: "none",
          background: "transparent",
          font: "600 14.5px var(--font-sans)",
          color: "var(--text-strong)",
          textAlign: "right",
          fontVariantNumeric: "tabular-nums",
        }}
      />
      <span style={{ font: "600 13px var(--font-sans)", color: "var(--text-muted)" }}>€</span>
    </span>
  );
}
