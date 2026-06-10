"use client";

import React from "react";

export interface SwitchProps {
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: (checked: boolean) => void;
  disabled?: boolean;
  size?: "sm" | "md";
  style?: React.CSSProperties;
}

export function Switch({
  checked,
  defaultChecked = false,
  onChange,
  disabled = false,
  size = "md",
  style,
}: SwitchProps) {
  const [internal, setInternal] = React.useState(defaultChecked);
  const on = checked !== undefined ? checked : internal;

  const dims = size === "sm" ? { w: 40, h: 24, k: 18 } : { w: 50, h: 30, k: 24 };

  function toggle() {
    if (disabled) return;
    if (checked === undefined) setInternal(!on);
    onChange?.(!on);
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      disabled={disabled}
      onClick={toggle}
      style={{
        width: dims.w,
        height: dims.h,
        flex: "none",
        borderRadius: "var(--r-full)",
        background: on ? "var(--brand)" : "var(--gray-300)",
        border: "none",
        padding: 3,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "background var(--dur-base) var(--ease-out)",
        display: "flex",
        alignItems: "center",
        ...style,
      }}
    >
      <span
        style={{
          width: dims.k,
          height: dims.k,
          borderRadius: "50%",
          background: "#fff",
          boxShadow: "0 1px 3px rgba(20,19,26,.25)",
          transform: on ? `translateX(${dims.w - dims.k - 6}px)` : "translateX(0)",
          transition: "transform var(--dur-base) var(--ease-spring)",
        }}
      />
    </button>
  );
}
