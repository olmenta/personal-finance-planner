"use client";

import React from "react";

export interface SegmentedOption {
  value: string;
  label: string;
}

export interface SegmentedControlProps {
  options?: (SegmentedOption | string)[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  size?: "sm" | "md";
  style?: React.CSSProperties;
}

export function SegmentedControl({
  options = [],
  value,
  defaultValue,
  onChange,
  size = "md",
  style,
}: SegmentedControlProps) {
  const first = options[0];
  const [internal, setInternal] = React.useState(
    defaultValue ?? (first ? (typeof first === "string" ? first : first.value) : undefined),
  );
  const current = value !== undefined ? value : internal;

  const pad = size === "sm" ? "8px 12px" : "11px 16px";
  const fs = size === "sm" ? 13 : 14.5;

  function pick(v: string) {
    if (value === undefined) setInternal(v);
    onChange?.(v);
  }

  return (
    <div
      style={{
        display: "flex",
        background: "var(--surface-sunk)",
        borderRadius: "var(--r-full)",
        padding: 4,
        gap: 2,
        width: "100%",
        ...style,
      }}
    >
      {options.map((opt) => {
        const v = typeof opt === "string" ? opt : opt.value;
        const label = typeof opt === "string" ? opt : opt.label;
        const active = v === current;
        return (
          <button
            key={v}
            type="button"
            onClick={() => pick(v)}
            style={{
              flex: 1,
              border: "none",
              cursor: "pointer",
              fontFamily: "var(--font-sans)",
              fontWeight: 600,
              fontSize: fs,
              letterSpacing: "-0.1px",
              padding: pad,
              borderRadius: "var(--r-full)",
              background: active ? "var(--surface)" : "transparent",
              color: active ? "var(--text-strong)" : "var(--text-muted)",
              boxShadow: active ? "var(--shadow-sm)" : "none",
              transition:
                "background var(--dur-base) var(--ease-out), color var(--dur-base) var(--ease-out)",
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
