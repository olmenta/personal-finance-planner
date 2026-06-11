"use client";

import React from "react";
import { Input } from "@/components/ui/Input";
import type { PayeeOut } from "@/lib/api";

const MAX_SUGGESTIONS = 6;

export interface PayeeFieldProps {
  label: string; // "Payee" (expense) / "Payer" (income)
  value: string;
  payees: PayeeOut[];
  onChange: (value: string) => void;
  onPick: (payee: PayeeOut) => void;
}

/** Free-text payee input with a locally filtered suggestion list (design D4).
    The payee list is small and ordered by most recent use, so filtering is
    a substring match client-side — no server round-trips. */
export function PayeeField({ label, value, payees, onChange, onPick }: PayeeFieldProps) {
  const [open, setOpen] = React.useState(false);

  const needle = value.trim().toLowerCase();
  const suggestions = payees
    .filter((p) => p.name.toLowerCase().includes(needle))
    .slice(0, MAX_SUGGESTIONS);

  return (
    <div
      style={{ position: "relative" }}
      onFocusCapture={() => setOpen(true)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
          setOpen(false);
        }
      }}
    >
      <Input
        label={label}
        placeholder="e.g. Mercadona"
        value={value}
        maxLength={120}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
      />
      {open && suggestions.length > 0 && (
        <div
          role="listbox"
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            marginTop: 6,
            zIndex: 30,
            background: "var(--surface)",
            border: "1px solid var(--border-hairline)",
            borderRadius: "var(--r-md)",
            boxShadow: "var(--shadow-lg)",
            overflow: "hidden",
          }}
        >
          {suggestions.map((p) => (
            <button
              key={p.id}
              type="button"
              role="option"
              aria-selected={p.name === value}
              // preventDefault keeps focus on the input so the blur
              // handler doesn't close the list before the click lands.
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onPick(p);
                setOpen(false);
              }}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "10px 14px",
                border: "none",
                background: "transparent",
                cursor: "pointer",
                font: "500 14.5px var(--font-sans)",
                color: "var(--text-strong)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--violet-50)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              {p.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
