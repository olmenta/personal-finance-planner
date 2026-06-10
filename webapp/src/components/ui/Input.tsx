"use client";

import React from "react";
import { Icon } from "./Icon";

export interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "prefix" | "size"> {
  label?: string;
  iconLeft?: string;
  prefix?: React.ReactNode;
  suffix?: React.ReactNode;
  error?: string;
  help?: string;
  inputStyle?: React.CSSProperties;
  wrapStyle?: React.CSSProperties;
}

export function Input({
  label,
  iconLeft,
  prefix,
  suffix,
  error,
  help,
  disabled = false,
  style,
  inputStyle,
  wrapStyle,
  ...rest
}: InputProps) {
  const [focus, setFocus] = React.useState(false);
  const borderColor = error
    ? "var(--expense)"
    : focus
      ? "var(--brand)"
      : "var(--border-hairline)";

  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 7, ...wrapStyle }}>
      {label && (
        <span
          style={{
            font: "600 13.5px var(--font-sans)",
            color: "var(--text-body)",
            letterSpacing: "-0.1px",
          }}
        >
          {label}
        </span>
      )}
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
          background: disabled ? "var(--gray-100)" : "var(--surface)",
          border: `1.5px solid ${borderColor}`,
          borderRadius: "var(--r-sm)",
          padding: "0 14px",
          height: 48,
          boxShadow: focus ? "var(--focus-ring)" : "none",
          transition:
            "border-color var(--dur-base) var(--ease-out), box-shadow var(--dur-base) var(--ease-out)",
        }}
      >
        {iconLeft && <Icon name={iconLeft} size={18} color="var(--text-subtle)" />}
        {prefix && (
          <span style={{ font: "700 16px var(--font-sans)", color: "var(--text-muted)" }}>
            {prefix}
          </span>
        )}
        <input
          disabled={disabled}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            font: "500 16px var(--font-sans)",
            color: "var(--text-strong)",
            minWidth: 0,
            ...inputStyle,
            ...style,
          }}
          {...rest}
        />
        {suffix && (
          <span style={{ font: "600 14px var(--font-sans)", color: "var(--text-muted)" }}>
            {suffix}
          </span>
        )}
      </span>
      {(error || help) && (
        <span
          style={{
            font: "500 12.5px var(--font-sans)",
            color: error ? "var(--expense)" : "var(--text-muted)",
          }}
        >
          {error || help}
        </span>
      )}
    </label>
  );
}
