"use client";

import { Panel } from "@/components/ui/Panel";
import type { SummaryView } from "@/lib/api";

/* Weekly spending and income for the month (moved from the old dashboard to
   Transactions: secondary analysis, out of Home's first viewport). */
export function SpendChart({ summary }: Readonly<{ summary: SummaryView }>) {
  const max = Math.max(
    1,
    ...summary.weeks.flatMap((w) => [w.spent_cents, w.income_cents]),
  );
  return (
    <Panel
      title="Spending this month"
      action={
        <div style={{ display: "flex", gap: 14 }}>
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              font: "500 12px var(--font-sans)",
              color: "var(--text-muted)",
            }}
          >
            <span style={{ width: 10, height: 10, borderRadius: 3, background: "var(--violet-500)" }} />{" "}
            Spent
          </span>
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              font: "500 12px var(--font-sans)",
              color: "var(--text-muted)",
            }}
          >
            <span style={{ width: 10, height: 10, borderRadius: 3, background: "var(--mint-400)" }} />{" "}
            Income
          </span>
        </div>
      }
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 18,
          height: 180,
          padding: "0 4px",
        }}
      >
        {summary.weeks.map((w, i) => (
          <div
            key={w.start}
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 10,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                gap: 6,
                height: 150,
                width: "100%",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  width: 14,
                  height: `${Math.round((w.spent_cents / max) * 100)}%`,
                  background: "var(--grad-balance)",
                  borderRadius: "6px 6px 3px 3px",
                }}
              />
              <div
                style={{
                  width: 14,
                  height: `${Math.round((w.income_cents / max) * 100)}%`,
                  background: "var(--mint-300)",
                  borderRadius: "6px 6px 3px 3px",
                }}
              />
            </div>
            <span style={{ font: "600 12px var(--font-sans)", color: "var(--text-subtle)" }}>
              W{i + 1}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* Spent share of the bar's limit; >100 reads as over even with no limit. */
