"use client";

import React from "react";
import { euroCents } from "@/lib/format";
import { availableCents } from "@/lib/useBudgetMonth";
import type { BudgetGroupView } from "@/lib/api";
import { Panel } from "@/components/ui/Panel";
import { AssignRow } from "./AssignRow";

export interface AssignGroupsProps {
  groups: BudgetGroupView[];
  onAssign: (categoryId: string, cents: number) => void;
}

/* One Panel per CategoryGroup composing AssignRows; assigned/available
   subtotals in the group header (desktop only). */
export function AssignGroups({ groups, onAssign }: Readonly<AssignGroupsProps>) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {[...groups]
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((g) => {
          const assigned = g.categories.reduce((a, c) => a + c.assigned_cents, 0);
          const available = g.categories.reduce((a, c) => a + availableCents(c), 0);
          return (
            <Panel
              key={g.id}
              title={g.name}
              action={
                <span
                  className="app-topbar-extras"
                  style={{
                    font: "500 13px var(--font-sans)",
                    color: "var(--text-muted)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  Assigned {euroCents(assigned)} · Available{" "}
                  <b
                    style={{
                      color: available < 0 ? "var(--expense)" : "var(--text-body)",
                    }}
                  >
                    {euroCents(available)}
                  </b>
                </span>
              }
              style={{ paddingTop: 16, paddingBottom: 8 }}
            >
              {g.categories.map((c) => (
                <AssignRow key={c.id} category={c} onAssign={onAssign} />
              ))}
            </Panel>
          );
        })}
    </div>
  );
}
