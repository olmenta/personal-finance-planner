"use client";

import React from "react";
import { euroCents } from "@/lib/format";
import { availableCents } from "@/lib/useBudgetMonth";
import { toneForCategory, type BudgetCategoryView } from "@/lib/api";
import { AmountInput } from "@/components/ui/AmountInput";
import { Icon } from "@/components/ui/Icon";
import { IconChip } from "@/components/ui/IconChip";
import { NumpadSheet } from "@/components/ui/NumpadSheet";

export interface AssignRowProps {
  category: BudgetCategoryView;
  onAssign: (categoryId: string, cents: number) => void;
}

function QuickFill({
  category,
  onPick,
}: Readonly<{ category: BudgetCategoryView; onPick: (cents: number) => void }>) {
  const options: [string, number | null][] = [
    ["Last month", category.last_month_assigned_cents],
    ["Average (3m)", category.avg_3m_cents],
    ["Spent last month", category.last_month_spent_cents],
    ["Zero", 0],
  ];
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, paddingTop: 10 }}>
      {options.map(([label, cents]) =>
        cents === null ? null : (
          <button
            key={label}
            onClick={() => onPick(cents)}
            style={{
              border: "1px solid var(--border-hairline)",
              background: "var(--surface)",
              borderRadius: "var(--r-full)",
              padding: "6px 11px",
              font: "600 12px var(--font-sans)",
              color: "var(--text-body)",
              cursor: "pointer",
            }}
          >
            {label}
            <span style={{ color: "var(--text-subtle)", fontVariantNumeric: "tabular-nums" }}>
              {" "}
              · {euroCents(cents, 0)}
            </span>
          </button>
        ),
      )}
    </div>
  );
}

/* One category row in the assignment list: chip + name, editable Assigned cell
   (inline input on desktop, numpad sheet on mobile), spent, available chip
   colored by sign, progress bar, expandable rollover breakdown. */
export function AssignRow({ category: c, onAssign }: Readonly<AssignRowProps>) {
  const [expanded, setExpanded] = React.useState(false);
  const [sheetOpen, setSheetOpen] = React.useState(false);

  const available = availableCents(c);
  const over = available < 0;

  let availColor = "var(--mint-700)";
  let availBg = "var(--mint-50)";
  if (over) {
    availColor = "var(--expense)";
    availBg = "var(--expense-soft)";
  } else if (available === 0) {
    availColor = "var(--text-muted)";
    availBg = "var(--gray-100)";
  }

  const budgetTotal = c.assigned_cents + c.rollover_cents;
  let pct = 0;
  if (budgetTotal > 0) {
    pct = Math.round((c.spent_cents / budgetTotal) * 100);
  } else if (c.spent_cents > 0) {
    pct = 101;
  }

  const isDraft = c.suggestion_state === "draft";

  return (
    <div style={{ padding: "13px 0", borderBottom: "1px solid var(--border-hairline)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
        <IconChip icon={c.icon} tone={over ? "expense" : toneForCategory(c.icon)} size={42} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span
              style={{
                font: "600 15px var(--font-sans)",
                color: "var(--text-strong)",
                letterSpacing: "-0.1px",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {c.name}
            </span>
            {isDraft && (
              <span
                style={{
                  font: "600 10.5px var(--font-sans)",
                  letterSpacing: "0.4px",
                  textTransform: "uppercase",
                  color: "var(--violet-600)",
                  background: "var(--violet-50)",
                  border: "1px solid var(--violet-200)",
                  borderRadius: "var(--r-full)",
                  padding: "2px 7px",
                  flex: "none",
                }}
              >
                Draft
              </span>
            )}
          </div>
          <div
            style={{
              font: "500 12.5px var(--font-sans)",
              color: "var(--text-muted)",
              marginTop: 2,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            Spent {euroCents(c.spent_cents)}
          </div>
        </div>

        {/* Assigned — the only editable cell */}
        <div className="assign-edit-desktop">
          <AmountInput
            valueCents={c.assigned_cents}
            draft={isDraft}
            ariaLabel={`Assigned to ${c.name}`}
            onCommit={(cents) => onAssign(c.id, cents)}
          />
        </div>
        <button
          className="assign-edit-mobile"
          onClick={() => setSheetOpen(true)}
          aria-label={`Assigned to ${c.name}: ${euroCents(c.assigned_cents)}. Edit`}
          style={{
            border: `1.5px solid ${isDraft ? "var(--violet-200)" : "transparent"}`,
            background: isDraft ? "var(--violet-50)" : "var(--surface-sunk)",
            borderRadius: "var(--r-sm)",
            padding: "8px 10px",
            font: "600 14.5px var(--font-sans)",
            color: "var(--text-strong)",
            cursor: "pointer",
            fontVariantNumeric: "tabular-nums",
            whiteSpace: "nowrap",
          }}
        >
          {euroCents(c.assigned_cents)}
        </button>

        <span
          style={{
            flex: "none",
            minWidth: 88,
            textAlign: "right",
            background: availBg,
            color: availColor,
            borderRadius: "var(--r-full)",
            padding: "6px 11px",
            font: "700 13.5px var(--font-sans)",
            fontVariantNumeric: "tabular-nums",
            whiteSpace: "nowrap",
          }}
        >
          {euroCents(available)}
        </span>

        <button
          onClick={() => setExpanded((e) => !e)}
          aria-label={expanded ? `Collapse ${c.name}` : `Expand ${c.name}`}
          aria-expanded={expanded}
          style={{
            border: "none",
            background: "none",
            cursor: "pointer",
            color: "var(--text-subtle)",
            padding: 4,
            display: "flex",
            transform: expanded ? "rotate(90deg)" : "none",
            transition: "transform var(--dur-base) var(--ease-out)",
          }}
        >
          <Icon name="chevron-right" size={18} />
        </button>
      </div>

      <div style={{ paddingLeft: 55 }}>
        <div
          style={{
            marginTop: 10,
            maxWidth: 420,
            height: 8,
            borderRadius: "var(--r-full)",
            background: "var(--gray-100)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${Math.min(pct, 100)}%`,
              height: "100%",
              borderRadius: "var(--r-full)",
              background: over ? "var(--expense)" : "var(--violet-500)",
              transition: "width var(--dur-slow) var(--ease-out)",
            }}
          />
        </div>
        {expanded && (
          <div style={{ paddingTop: 12 }}>
            <div
              style={{
                font: "500 13px var(--font-sans)",
                color: "var(--text-muted)",
                background: "var(--surface-sunk)",
                borderRadius: "var(--r-md)",
                padding: "10px 14px",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              Rollover {euroCents(c.rollover_cents)} + assigned {euroCents(c.assigned_cents)} −
              spent {euroCents(c.spent_cents)} ={" "}
              <b style={{ color: availColor }}>{euroCents(available)}</b> available
            </div>
            <QuickFill category={c} onPick={(cents) => onAssign(c.id, cents)} />
          </div>
        )}
      </div>

      <NumpadSheet
        open={sheetOpen}
        label={`Assign to ${c.name}`}
        initialCents={c.assigned_cents}
        confirmLabel="Set amount"
        onConfirm={(cents) => onAssign(c.id, cents)}
        onClose={() => setSheetOpen(false)}
      />
    </div>
  );
}
