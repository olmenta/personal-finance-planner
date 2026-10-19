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
  /** One-tap cover from the server's suggestion (budget-rules). */
  onCover: (category: BudgetCategoryView) => void;
  /** Opens the move-money sheet with this category as the source. */
  onMove: (category: BudgetCategoryView) => void;
  /** Category id → name, for the cover button label. */
  nameOf: (categoryId: string) => string;
  /** Opens the payment-schedule editor for this category. */
  onSchedule: (category: BudgetCategoryView) => void;
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

const signed = (cents: number) => (cents > 0 ? `+${euroCents(cents)}` : euroCents(cents));

const cellLabel: React.CSSProperties = { color: "var(--text-subtle)" };
const carryStyle: React.CSSProperties = {
  font: "500 11.5px var(--font-sans)",
  color: "var(--text-muted)",
  fontVariantNumeric: "tabular-nums",
  whiteSpace: "nowrap",
};
const spentStyle: React.CSSProperties = {
  padding: "8px 0",
  font: "600 14.5px var(--font-sans)",
  color: "var(--text-body)",
  fontVariantNumeric: "tabular-nums",
  whiteSpace: "nowrap",
};

/* One category row in the assignment list: chip + name, then three cells —
   Assigned (inline input on desktop, numpad sheet on mobile, plus what
   carries over), Spent, and the Available chip colored by sign
   (budget-spent-column) — progress bar, expandable rollover breakdown. */
export function AssignRow({
  category: c,
  onAssign,
  onCover,
  onMove,
  nameOf,
  onSchedule,
}: Readonly<AssignRowProps>) {
  const [expanded, setExpanded] = React.useState(false);
  const [sheetOpen, setSheetOpen] = React.useState(false);

  const available = availableCents(c);
  const over = available < 0;
  // Card spending the category couldn't cover is new card debt, not a cash
  // hole: it gets a warning style, never the expense red (credit-cards D6).
  const creditOver = c.credit_overspent_cents;
  const cashOver = over && -available > creditOver;
  const isPayment = c.kind === "credit_payment";
  // Money set aside from this month's budgeted card purchases.
  const funded = isPayment ? available - c.assigned_cents - c.rollover_cents + c.spent_cents : 0;

  let availColor = "var(--mint-700)";
  let availBg = "var(--mint-50)";
  if (cashOver) {
    availColor = "var(--expense)";
    availBg = "var(--expense-soft)";
  } else if (over) {
    availColor = "var(--warning)";
    availBg = "var(--warning-soft)";
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
  // Categories with payments are assigned their computed monthly amount:
  // shown, never typed (change the payments, or move money explicitly).
  const fromPayments = c.normal_cents !== null;

  // The middle column: payments to the card for its payment category.
  const spentLabel = isPayment ? "Paid" : "Spent";
  // What Available adds on top of this month's assignment, under Assigned,
  // so the visible amounts add up (budget-spent-column D4).
  const carry: string[] = [];
  if (c.rollover_cents !== 0) carry.push(`${signed(c.rollover_cents)} from last month`);
  if (funded > 0) carry.push(`${signed(funded)} set aside`);
  // The subtitle keeps only the payment notes (D5).
  const notes: React.ReactNode[] = [];
  if (c.normal_cents !== null && c.catch_up_cents !== null) {
    notes.push(<React.Fragment key="normal">normal {euroCents(c.normal_cents)}</React.Fragment>);
    if (c.catch_up_cents > c.normal_cents) {
      notes.push(
        <span key="catch-up" style={{ color: "#9A5B00" }}>
          {" · "}to be on time {euroCents(c.catch_up_cents)}
        </span>,
      );
    }
  }

  return (
    <div data-testid={`category-row-${c.name}`} style={{ padding: "13px 0", borderBottom: "1px solid var(--border-hairline)" }}>
      <div className="budget-row-main">
        <IconChip
          icon={c.icon}
          tone={cashOver ? "expense" : over ? "warning" : toneForCategory(c.icon)}
          size={42}
        />
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
            {fromPayments && (
              <span
                style={{
                  font: "600 10.5px var(--font-sans)",
                  letterSpacing: "0.4px",
                  textTransform: "uppercase",
                  color: "var(--text-muted)",
                  background: "var(--gray-100)",
                  borderRadius: "var(--r-full)",
                  padding: "2px 7px",
                  flex: "none",
                }}
              >
                From your payments
              </span>
            )}
            {isDraft && !fromPayments && (
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
          {notes.length > 0 && (
            <div
              style={{
                font: "500 12.5px var(--font-sans)",
                color: "var(--text-muted)",
                marginTop: 2,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {notes}
            </div>
          )}
        </div>

        <div className="budget-cols">
          <div className="budget-cell">
            <span className="budget-cell-label ol-eyebrow" style={cellLabel}>Assigned</span>
            {/* Assigned — editable for day-to-day categories only */}
            {fromPayments ? (
              <span
                title="Worked out from this category's payments"
                style={{
                  padding: "8px 10px",
                  font: "600 14.5px var(--font-sans)",
                  color: "var(--text-strong)",
                  fontVariantNumeric: "tabular-nums",
                  whiteSpace: "nowrap",
                }}
              >
                {euroCents(c.assigned_cents)}
              </span>
            ) : (
            <>
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
            </>
            )}
            {carry.map((line) => (
              <span key={line} data-testid={`carry-${c.name}`} style={carryStyle}>
                {line}
              </span>
            ))}
          </div>
          <div className="budget-cell">
            <span className="budget-cell-label ol-eyebrow" style={cellLabel}>{spentLabel}</span>
            <span data-testid={`spent-${c.name}`} style={spentStyle}>
              {euroCents(c.spent_cents)}
            </span>
          </div>
          <div className="budget-cell">
            <span className="budget-cell-label ol-eyebrow" style={cellLabel}>Available</span>
            <span
              className="budget-available"
              style={{
                flex: "none",
                minWidth: 88,
                display: "inline-block",
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
          </div>
        </div>

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
        {!isPayment && (
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
              background: cashOver ? "var(--expense)" : over ? "var(--warning)" : "var(--violet-500)",
              transition: "width var(--dur-slow) var(--ease-out)",
            }}
          />
        </div>
        )}
        {creditOver > 0 && (
          <div
            style={{
              marginTop: 8,
              font: "600 12.5px var(--font-sans)",
              color: "var(--warning)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {euroCents(creditOver)} on the card isn&apos;t covered — it&apos;s new card debt
            unless you cover it this month.
          </div>
        )}
        {c.cover_suggestion && (
          <button
            onClick={() => onCover(c)}
            style={{
              marginTop: 10,
              border: "none",
              background: "var(--expense-soft)",
              color: "var(--expense)",
              borderRadius: "var(--r-full)",
              padding: "6px 12px",
              font: "600 12.5px var(--font-sans)",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            <Icon name="arrow-left-right" size={14} />
            Cover {euroCents(c.cover_suggestion.amount_cents)} from{" "}
            {c.cover_suggestion.source_category_id === null
              ? "unassigned"
              : nameOf(c.cover_suggestion.source_category_id)}
          </button>
        )}
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
              Rollover {euroCents(c.rollover_cents)} + assigned {euroCents(c.assigned_cents)}
              {isPayment && <> + set aside {euroCents(funded)}</>} −{" "}
              {isPayment ? "paid" : "spent"} {euroCents(c.spent_cents)} ={" "}
              <b style={{ color: availColor }}>{euroCents(available)}</b> available
              {c.rollover_reset_cents > 0 && (
                <div style={{ marginTop: 4 }}>
                  Started this month clean: last month&apos;s {euroCents(c.rollover_reset_cents)}{" "}
                  overspending was reset — cash overspending came out of To Be Assigned,
                  card overspending stays on the card as debt.
                </div>
              )}
            </div>
            {!fromPayments && <QuickFill category={c} onPick={(cents) => onAssign(c.id, cents)} />}
            {!isPayment && (
            <button
              onClick={() => onSchedule(c)}
              style={{
                marginTop: 8,
                marginRight: 6,
                border: "1px solid var(--border-hairline)",
                background: "var(--surface)",
                borderRadius: "var(--r-full)",
                padding: "6px 11px",
                font: "600 12px var(--font-sans)",
                color: "var(--text-body)",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <Icon name="calendar" size={13} />
              {c.normal_cents !== null ? "Edit payments" : "Set up payments"}
            </button>
            )}
            {available > 0 && (
              <button
                onClick={() => onMove(c)}
                style={{
                  marginTop: 8,
                  border: "1px solid var(--border-hairline)",
                  background: "var(--surface)",
                  borderRadius: "var(--r-full)",
                  padding: "6px 11px",
                  font: "600 12px var(--font-sans)",
                  color: "var(--text-body)",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <Icon name="arrow-left-right" size={13} /> Move money
              </button>
            )}
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
