"use client";

import React from "react";
import { euroCents } from "@/lib/format";
import { availableCents } from "@/lib/useBudgetMonth";
import type { BudgetCategoryView, BudgetGroupView } from "@/lib/api";
import { Panel } from "@/components/ui/Panel";
import { AssignRow } from "./AssignRow";

export interface AssignGroupsProps {
  groups: BudgetGroupView[];
  onAssign: (categoryId: string, cents: number) => void;
  onCover: (category: BudgetCategoryView) => void;
  onMove: (category: BudgetCategoryView) => void;
  onSchedule: (category: BudgetCategoryView) => void;
}

function HeadCell({ label, cents, negative = false }: Readonly<{ label: string; cents: number; negative?: boolean }>) {
  return (
    <div className="budget-cell">
      <span className="ol-eyebrow" style={{ color: "var(--text-subtle)" }}>
        {label}
      </span>
      <span
        style={{
          font: "600 13px var(--font-sans)",
          color: negative ? "var(--expense)" : "var(--text-muted)",
          fontVariantNumeric: "tabular-nums",
          whiteSpace: "nowrap",
        }}
      >
        {euroCents(cents)}
      </span>
    </div>
  );
}

/* One Panel per CategoryGroup composing AssignRows. Desktop: a header row
   labels the rows' Assigned · Spent · Available cells and carries the group's
   subtotals in the same columns (budget-spent-column D1). */
export function AssignGroups({
  groups,
  onAssign,
  onCover,
  onMove,
  onSchedule,
}: Readonly<AssignGroupsProps>) {
  const names = new Map(groups.flatMap((g) => g.categories.map((c) => [c.id, c.name] as const)));
  const nameOf = (id: string) => names.get(id) ?? "another category";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {[...groups]
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((g) => {
          const assigned = g.categories.reduce((a, c) => a + c.assigned_cents, 0);
          const spent = g.categories.reduce((a, c) => a + c.spent_cents, 0);
          const available = g.categories.reduce((a, c) => a + availableCents(c), 0);
          const onlyPayments = g.categories.every((c) => c.kind === "credit_payment");
          return (
            <Panel key={g.id} title={g.name} style={{ paddingTop: 16, paddingBottom: 8 }}>
              {/* Column labels and the group's subtotals, aligned with the
                  rows' cells (desktop; mobile rows carry their own labels). */}
              <div
                className="budget-cols-head"
                data-testid={`group-totals-${g.name}`}
                style={{ display: "flex", alignItems: "flex-end", gap: 13, paddingBottom: 6, borderBottom: "1px solid var(--border-hairline)" }}
              >
                <div style={{ flex: 1 }} />
                <div className="budget-cols">
                  <HeadCell label="Assigned" cents={assigned} />
                  <HeadCell label={onlyPayments ? "Paid" : "Spent"} cents={spent} />
                  <HeadCell label="Available" cents={available} negative={available < 0} />
                </div>
                {/* the rows' expand chevron */}
                <div style={{ width: 26, flex: "none" }} />
              </div>
              {g.categories.map((c) => (
                <AssignRow
                  key={c.id}
                  category={c}
                  onAssign={onAssign}
                  onCover={onCover}
                  onMove={onMove}
                  nameOf={nameOf}
                  onSchedule={onSchedule}
                />
              ))}
            </Panel>
          );
        })}
    </div>
  );
}
