"use client";

import React from "react";
import { Icon } from "./Icon";

export interface SearchInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size"> {
  fieldSize?: "sm" | "md";
  wrapStyle?: React.CSSProperties;
}

export function SearchInput({
  placeholder = "Search",
  fieldSize = "md",
  wrapStyle,
  style,
  ...rest
}: SearchInputProps) {
  const h = fieldSize === "sm" ? 40 : 46;
  return (
    <span
      style={{
        display: "flex",
        alignItems: "center",
        gap: 9,
        background: "var(--surface-sunk)",
        border: "1px solid transparent",
        borderRadius: "var(--r-full)",
        padding: "0 16px",
        height: h,
        ...wrapStyle,
      }}
    >
      <Icon name="search" size={18} color="var(--text-subtle)" />
      <input
        placeholder={placeholder}
        style={{
          flex: 1,
          border: "none",
          outline: "none",
          background: "transparent",
          font: "500 15px var(--font-sans)",
          color: "var(--text-strong)",
          minWidth: 0,
          ...style,
        }}
        {...rest}
      />
    </span>
  );
}
