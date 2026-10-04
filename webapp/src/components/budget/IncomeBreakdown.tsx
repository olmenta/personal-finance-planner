"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/shadcn/dialog";
import {
  fetchExpectedIncome,
  fetchTransactions,
  type BudgetMonthView,
} from "@/lib/api";
import { euroCents } from "@/lib/format";
import { monthLabel } from "@/lib/schedules";

/* Where the month's money to assign comes from (spec: budget-assignment,
   income breakdown): each income one by one, expected vs received, the
   carry-in and deductions, and what's assigned — ending in the hero's number. */

const line: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  padding: "8px 0",
  borderBottom: "1px dashed var(--border-hairline)",
  font: "500 14px var(--font-sans)",
  color: "var(--text-body)",
  fontVariantNumeric: "tabular-nums",
};

export function IncomeBreakdown({
  open,
  onOpenChange,
  view,
}: Readonly<{ open: boolean; onOpenChange: (open: boolean) => void; view: BudgetMonthView }>) {
  const tx = useQuery({
    queryKey: ["transactions", view.month],
    queryFn: () => fetchTransactions(view.month),
    enabled: open,
  });
  const expected = useQuery({ queryKey: ["plan-income"], queryFn: fetchExpectedIncome, enabled: open });

  // Same rule as income_cents: confirmed uncategorized inflows. Refunds
  // (categorized inflows) are category activity, never income.
  const incomes = (tx.data ?? [])
    .filter((t) => t.amount_cents > 0 && !t.category_id)
    .sort((a, b) => a.date.localeCompare(b.date));
  const received = view.income_cents;
  const expectedCents = expected.data?.expected_monthly_cents ?? null;
  const assigned = view.groups.flatMap((g) => g.categories).reduce((t, c) => t + c.assigned_cents, 0);
  // Uncategorized outflows also lower To Be Assigned; show them so the total adds up.
  const other =
    view.to_be_assigned_cents -
    (view.carried_in_cents + received - view.overspent_deducted_cents - assigned);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="p-0 gap-0 overflow-hidden"
        style={{ borderRadius: "var(--r-2xl)", maxWidth: 460, border: "1px solid var(--border-hairline)", boxShadow: "var(--shadow-xl)" }}
      >
        <DialogHeader style={{ padding: "20px 24px 14px", borderBottom: "1px solid var(--border-hairline)" }}>
          <DialogTitle style={{ font: "700 19px var(--font-sans)", letterSpacing: "-0.4px", color: "var(--text-strong)" }}>
            Money to assign · {monthLabel(view.month)}
          </DialogTitle>
        </DialogHeader>
        <div style={{ padding: "12px 24px 20px" }}>
          <div className="ol-eyebrow" style={{ color: "var(--text-subtle)", margin: "8px 0 2px" }}>Income this month</div>
          {incomes.length === 0 ? (
            <div style={{ ...line, color: "var(--text-muted)" }}>
              {tx.isPending ? "Loading…" : "No income has arrived yet this month."}
            </div>
          ) : (
            incomes.map((t) => (
              <div key={t.id} style={line}>
                <span>
                  {t.payee_name ?? t.description ?? "Income"}
                  <span style={{ color: "var(--text-muted)" }}> · day {Number(t.date.slice(8, 10))}</span>
                </span>
                <b style={{ color: "var(--income)" }}>{euroCents(t.amount_cents)}</b>
              </div>
            ))
          )}
          {expectedCents !== null && (
            <div style={{ ...line, color: "var(--text-muted)", font: "500 13px var(--font-sans)" }}>
              <span>
                expected {euroCents(expectedCents)} · received {euroCents(received)}
              </span>
              {received < expectedCents && <span>{euroCents(expectedCents - received)} still to come</span>}
            </div>
          )}

          <div className="ol-eyebrow" style={{ color: "var(--text-subtle)", margin: "16px 0 2px" }}>To be assigned</div>
          <div style={line}><span>Carried in from last month</span><span>{euroCents(view.carried_in_cents)}</span></div>
          <div style={line}><span>+ Income this month</span><b style={{ color: "var(--income)" }}>{euroCents(received)}</b></div>
          {view.overspent_deducted_cents > 0 && (
            <div style={line}>
              <span>− Last month&apos;s uncovered overspending</span>
              <span>−{euroCents(view.overspent_deducted_cents)}</span>
            </div>
          )}
          {other !== 0 && (
            <div style={line}><span>Uncategorized spending</span><span>{euroCents(other)}</span></div>
          )}
          <div style={line}><span>− Assigned this month</span><span>−{euroCents(assigned)}</span></div>
          <div style={{ ...line, borderBottom: 0, font: "700 16px var(--font-sans)", color: "var(--text-strong)" }}>
            <span>= To be assigned</span>
            <span>{euroCents(view.to_be_assigned_cents)}</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
