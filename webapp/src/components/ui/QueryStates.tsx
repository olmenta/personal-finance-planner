"use client";

import React from "react";
import { Button } from "./Button";
import { Panel } from "./Panel";

/* Shared presentation for server-state queries: a fixed-height skeleton that
   matches the panel rhythm (no layout shift on resolve) and a retryable
   error panel. Empty states live per-screen — they invite action. */

export interface SkeletonPanelProps {
  rows?: number;
  rowHeight?: number;
}

export function SkeletonPanel({ rows = 4, rowHeight = 42 }: Readonly<SkeletonPanelProps>) {
  return (
    <Panel style={{ paddingTop: 16, paddingBottom: 16 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {Array.from({ length: rows }, (_, i) => (
          <div
            key={i}
            style={{
              height: rowHeight,
              borderRadius: "var(--r-md)",
              background: "var(--surface-sunk)",
            }}
          />
        ))}
      </div>
    </Panel>
  );
}

export interface ErrorPanelProps {
  message?: string;
  onRetry: () => void;
}

export function ErrorPanel({
  message = "We couldn't reach your data.",
  onRetry,
}: Readonly<ErrorPanelProps>) {
  return (
    <Panel style={{ textAlign: "center", padding: 40 }}>
      <div
        style={{
          font: "700 18px var(--font-sans)",
          letterSpacing: "-0.3px",
          color: "var(--text-strong)",
        }}
      >
        {message}
      </div>
      <div
        style={{
          font: "500 14px var(--font-sans)",
          color: "var(--text-muted)",
          margin: "8px 0 18px",
        }}
      >
        Check that the backend is running, then try again.
      </div>
      <Button variant="primary" iconLeft="rotate-cw" onClick={onRetry}>
        Try again
      </Button>
    </Panel>
  );
}
