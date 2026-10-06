"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/shadcn/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/shadcn/select";
import { Badge } from "@/components/ui/Badge";
import {
  fetchMonthIncome,
  updateIncomeSchedule,
  updateTransaction,
  type BudgetMonthView,
  type IncomeOccurrence,
  type UnplannedIncome,
} from "@/lib/api";
import { euroCents } from "@/lib/format";
import { invalidateIncomeQueries, invalidateMoneyQueries } from "@/lib/planQueries";
import { monthLabel } from "@/lib/schedules";

/* Where the month's money to assign comes from (spec: budget-assignment,
   income breakdown): expected income one by one with its status, unplanned
   income, the carry-in and deductions, and what's assigned — ending in the
   hero's number. Only received money adds up; expected income never does. */

const line: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: 12,
  padding: "8px 0",
  borderBottom: "1px dashed var(--border-hairline)",
  font: "500 14px var(--font-sans)",
  color: "var(--text-body)",
  fontVariantNumeric: "tabular-nums",
};

const muted: React.CSSProperties = { color: "var(--text-muted)" };

function StatusChip({ occ }: Readonly<{ occ: IncomeOccurrence }>) {
  switch (occ.status) {
    case "received": {
      const diff = occ.difference_cents ?? 0;
      const label =
        diff === 0
          ? "received"
          : `received · ${euroCents(Math.abs(diff))} ${diff < 0 ? "less" : "more"}`;
      return <Badge tone="income">{label}</Badge>;
    }
    case "late":
      return <Badge tone="warning">not arrived yet</Badge>;
    case "missed":
      return <Badge tone="neutral">didn&apos;t arrive</Badge>;
    default:
      return <Badge tone="neutral">{occ.day ? `expected day ${occ.day}` : "expected this month"}</Badge>;
  }
}

/** "This is…": link an unplanned inflow to an expected occurrence through
    payee equality (spec: income-schedules, linking). */
async function linkIncome(item: UnplannedIncome, occ: IncomeOccurrence): Promise<void> {
  if (occ.payee_id && occ.payer) {
    await updateTransaction(item.transaction_id, { payee: occ.payer });
  } else if (item.payee_id) {
    await updateIncomeSchedule(occ.schedule_id, { payer: item.label });
  } else {
    await updateIncomeSchedule(occ.schedule_id, { payer: occ.name });
    await updateTransaction(item.transaction_id, { payee: occ.name });
  }
}

function UnplannedRow({
  item,
  candidates,
}: Readonly<{ item: UnplannedIncome; candidates: IncomeOccurrence[] }>) {
  const queryClient = useQueryClient();
  const link = useMutation({
    mutationFn: (occ: IncomeOccurrence) => linkIncome(item, occ),
    onSettled: () => {
      invalidateMoneyQueries(queryClient);
      invalidateIncomeQueries(queryClient);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["payees"] });
    },
  });
  return (
    <div style={{ ...line, flexWrap: "wrap" }}>
      <span style={{ minWidth: 0 }}>
        {item.label || "Income"}
        <span style={muted}> · day {Number(item.date.slice(8, 10))}</span>
      </span>
      <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {candidates.length > 0 && (
          <Select
            value=""
            onValueChange={(id) => {
              const occ = candidates.find((o) => o.schedule_id === id);
              if (occ) link.mutate(occ);
            }}
            disabled={link.isPending}
          >
            <SelectTrigger
              aria-label={`Link ${item.label || "this income"} to an expected income`}
              className="h-8 rounded-[8px] border text-[13px] font-semibold"
              style={{ borderColor: "var(--border-hairline)", color: "var(--brand)", background: "var(--surface)" }}
            >
              <SelectValue placeholder="This is…" />
            </SelectTrigger>
            <SelectContent>
              {candidates.map((o) => (
                <SelectItem key={o.schedule_id} value={o.schedule_id}>
                  {o.name} · {euroCents(o.amount_cents)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <b style={{ color: "var(--income)" }}>{euroCents(item.amount_cents)}</b>
      </span>
    </div>
  );
}

export function IncomeBreakdown({
  open,
  onOpenChange,
  view,
}: Readonly<{ open: boolean; onOpenChange: (open: boolean) => void; view: BudgetMonthView }>) {
  const income = useQuery({
    queryKey: ["income", view.month],
    queryFn: () => fetchMonthIncome(view.month),
    enabled: open,
  });

  const data = income.data;
  const received = view.income_cents;
  // Opening balances count as income in the budget but match no schedule.
  const opening = data ? received - data.received_cents : 0;
  const candidates = (data?.occurrences ?? []).filter((o) => o.status !== "received");
  const assigned = view.groups.flatMap((g) => g.categories).reduce((t, c) => t + c.assigned_cents, 0);
  // Uncategorized outflows also lower To Be Assigned; show them so the total adds up.
  const other =
    view.to_be_assigned_cents -
    (view.carried_in_cents + received - view.overspent_deducted_cents - assigned);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="p-0 gap-0 overflow-hidden"
        style={{ borderRadius: "var(--r-2xl)", maxWidth: 480, border: "1px solid var(--border-hairline)", boxShadow: "var(--shadow-xl)" }}
      >
        <DialogHeader style={{ padding: "20px 24px 14px", borderBottom: "1px solid var(--border-hairline)" }}>
          <DialogTitle style={{ font: "700 19px var(--font-sans)", letterSpacing: "-0.4px", color: "var(--text-strong)" }}>
            Money to assign · {monthLabel(view.month)}
          </DialogTitle>
        </DialogHeader>
        <div style={{ padding: "12px 24px 20px", maxHeight: "calc(100vh - 140px)", overflowY: "auto" }}>
          <div className="ol-eyebrow" style={{ color: "var(--text-subtle)", margin: "8px 0 2px" }}>Income this month</div>
          {!data ? (
            <div style={{ ...line, ...muted }}>Loading…</div>
          ) : (
            <>
              {data.occurrences.map((o) => (
                <div key={o.schedule_id} style={{ ...line, flexWrap: "wrap" }} data-testid="income-occurrence">
                  <span style={{ minWidth: 0 }}>
                    {o.name}
                    {o.day && <span style={muted}> · day {o.day}</span>}
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <StatusChip occ={o} />
                    <b style={{ color: o.status === "received" ? "var(--income)" : "var(--text-muted)" }}>
                      {euroCents(o.status === "received" ? o.received_cents : o.amount_cents)}
                    </b>
                  </span>
                </div>
              ))}
              {data.unplanned.length > 0 && (
                <div className="ol-eyebrow" style={{ color: "var(--text-subtle)", margin: "12px 0 2px" }}>
                  Unplanned income
                </div>
              )}
              {data.unplanned.map((u) => (
                <UnplannedRow key={u.transaction_id} item={u} candidates={candidates} />
              ))}
              {opening > 0 && (
                <div style={line}>
                  <span>Starting balance</span>
                  <b style={{ color: "var(--income)" }}>{euroCents(opening)}</b>
                </div>
              )}
              {received === 0 && (
                <div style={{ ...line, ...muted }}>
                  {data.has_schedules
                    ? "No income has arrived yet this month — the expected income above is still to come."
                    : "No income has arrived yet this month. Add your income in Settings to see what's expected."}
                </div>
              )}
              {data.has_schedules && (
                <div style={{ ...line, ...muted, font: "500 13px var(--font-sans)" }}>
                  <span>
                    expected {euroCents(data.expected_cents)} · received {euroCents(data.received_cents)}
                  </span>
                  {data.still_expected_cents > 0 && <span>{euroCents(data.still_expected_cents)} still to come</span>}
                </div>
              )}
            </>
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
