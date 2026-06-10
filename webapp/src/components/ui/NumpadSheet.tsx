"use client";

import React from "react";
import { euroCents } from "@/lib/format";
import { Icon } from "./Icon";

export interface NumpadSheetProps {
  open: boolean;
  label: string;
  initialCents: number;
  confirmLabel?: string;
  onConfirm: (cents: number) => void;
  onClose: () => void;
}

/* Bottom-sheet numpad for touch amount entry (<1024px). Cash-register style:
   digits push cents from the right (1→2→3 = 1,23 €). Built for reuse by the
   expense-entry flow (design.md: one numpad, two consumers). */
export function NumpadSheet({
  open,
  label,
  initialCents,
  confirmLabel = "Save",
  onConfirm,
  onClose,
}: NumpadSheetProps) {
  const [cents, setCents] = React.useState(initialCents);

  React.useEffect(() => {
    if (open) setCents(initialCents);
  }, [open, initialCents]);

  if (!open) return null;

  const push = (d: number) => setCents((c) => (c >= 100000000 ? c : c * 10 + d));
  const pop = () => setCents((c) => Math.floor(c / 10));

  const keys: (number | "back" | "zero")[] = [1, 2, 3, 4, 5, 6, 7, 8, 9, "zero", 0, "back"];

  return (
    <div
      role="dialog"
      aria-label={label}
      style={{ position: "fixed", inset: 0, zIndex: "var(--z-sheet)" as React.CSSProperties["zIndex"] }}
    >
      <button
        aria-label="Close"
        onClick={onClose}
        style={{
          position: "absolute",
          inset: 0,
          background: "var(--overlay)",
          border: "none",
          cursor: "pointer",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          background: "var(--surface)",
          borderRadius: "var(--r-2xl) var(--r-2xl) 0 0",
          boxShadow: "var(--shadow-xl)",
          padding: "18px 20px calc(18px + env(safe-area-inset-bottom))",
        }}
      >
        <div
          style={{
            font: "600 13.5px var(--font-sans)",
            color: "var(--text-muted)",
            textAlign: "center",
          }}
        >
          {label}
        </div>
        <div
          style={{
            font: "800 38px var(--font-sans)",
            letterSpacing: "-1.2px",
            color: "var(--text-strong)",
            textAlign: "center",
            margin: "6px 0 14px",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {euroCents(cents)}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
          {keys.map((k) => {
            if (k === "zero") {
              return (
                <button
                  key="00"
                  onClick={() => {
                    push(0);
                    push(0);
                  }}
                  style={keyStyle}
                >
                  00
                </button>
              );
            }
            if (k === "back") {
              return (
                <button key="back" aria-label="Delete digit" onClick={pop} style={keyStyle}>
                  <Icon name="chevron-left" size={20} />
                </button>
              );
            }
            return (
              <button key={k} onClick={() => push(k)} style={keyStyle}>
                {k}
              </button>
            );
          })}
        </div>
        <button
          onClick={() => {
            onConfirm(cents);
            onClose();
          }}
          style={{
            width: "100%",
            marginTop: 12,
            background: "var(--brand)",
            color: "#fff",
            border: "none",
            borderRadius: "var(--r-full)",
            padding: "15px",
            font: "600 16px var(--font-sans)",
            cursor: "pointer",
            boxShadow: "0 6px 16px rgba(124,92,252,.28)",
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </div>
  );
}

const keyStyle: React.CSSProperties = {
  height: 54,
  borderRadius: "var(--r-md)",
  border: "1px solid var(--border-hairline)",
  background: "var(--surface)",
  font: "600 19px var(--font-sans)",
  color: "var(--text-strong)",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontVariantNumeric: "tabular-nums",
};
