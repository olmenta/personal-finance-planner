"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { TopBar } from "@/components/shell/TopBar";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Input } from "@/components/ui/Input";
import { Panel } from "@/components/ui/Panel";
import { ErrorPanel, SkeletonPanel } from "@/components/ui/QueryStates";
import { IncomeEditorDialog } from "@/components/plan/IncomeEditor";
import {
  createIncomeSchedule,
  fetchPlanSummary,
  fetchUpcoming,
  type UpcomingMonth,
} from "@/lib/api";
import { euroCents, parseEuroToCents } from "@/lib/format";
import { invalidateIncomeQueries } from "@/lib/planQueries";
import { monthLabel } from "@/lib/schedules";
import { useSelectedMonth } from "@/lib/selectedMonth";

/* Upcoming payments (spec: payment-projection): the year at a glance and, per
   month, whether every payment is covered — computed by allocating each
   month's expected income (income schedules, never bonuses) in priority order. */

function SummaryCard({
  label,
  value,
  note,
  warn,
  action,
}: Readonly<{ label: string; value: string; note: string; warn?: boolean; action?: React.ReactNode }>) {
  return (
    <Panel>
      <div className="ol-eyebrow" style={{ color: "var(--text-subtle)" }}>{label}</div>
      <div
        style={{
          font: "800 26px var(--font-sans)",
          letterSpacing: "-0.8px",
          color: warn ? "#9A5B00" : "var(--text-strong)",
          fontVariantNumeric: "tabular-nums",
          marginTop: 6,
        }}
      >
        {value}
      </div>
      <div style={{ font: "500 13px var(--font-sans)", color: "var(--text-muted)", marginTop: 2 }}>{note}</div>
      {action && <div style={{ marginTop: 10 }}>{action}</div>}
    </Panel>
  );
}

function FundingBar({ label, funded, wanted }: Readonly<{ label: string; funded: number; wanted: number }>) {
  const pct = wanted > 0 ? Math.min(1, funded / wanted) : 1;
  const full = pct >= 0.999;
  return (
    <span
      title={`${euroCents(funded)} of ${euroCents(wanted)}`}
      style={{ display: "inline-flex", alignItems: "center", gap: 8, font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}
    >
      {label} {Math.round(pct * 100)} %
      <span style={{ width: 96, height: 6, borderRadius: 6, background: "var(--chart-empty)", overflow: "hidden", display: "inline-block" }}>
        <span
          style={{
            display: "block",
            height: "100%",
            width: `${Math.round(pct * 100)}%`,
            background: full ? "var(--accent)" : "var(--warning)",
          }}
        />
      </span>
    </span>
  );
}

function MonthRow({ m, open, onToggle }: Readonly<{ m: UpcomingMonth; open: boolean; onToggle: () => void }>) {
  const short = m.short_cents ?? 0;
  const known = m.short_cents !== null;
  const setAsideShort =
    m.set_aside_wanted_cents !== null &&
    m.set_aside_funded_cents !== null &&
    m.set_aside_funded_cents < m.set_aside_wanted_cents - 50;
  return (
    <div style={{ background: "var(--surface)", borderRadius: "var(--r-lg)", boxShadow: "var(--shadow-sm)", padding: "0 16px" }}>
      <button
        onClick={onToggle}
        aria-expanded={open}
        style={{
          width: "100%",
          border: "none",
          background: "none",
          cursor: "pointer",
          padding: "14px 0",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
          textAlign: "left",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <span style={{ font: "700 15px var(--font-sans)", color: "var(--text-strong)", minWidth: 130 }}>{monthLabel(m.month)}</span>
          {m.expected_income_cents !== null && (
            <span style={{ fontVariantNumeric: "tabular-nums", font: "600 13px var(--font-sans)", color: "var(--income)" }} title="Expected income">
              +{euroCents(m.expected_income_cents)}
            </span>
          )}
          <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 600, color: "var(--text-strong)" }} title="Payments">{euroCents(m.payments_cents)}</span>
          {known && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                font: "600 12px var(--font-sans)",
                borderRadius: "var(--r-full)",
                padding: "2px 8px",
                background: short > 0 ? "var(--warning-soft)" : "var(--mint-50)",
                color: short > 0 ? "#9A5B00" : "var(--mint-700)",
              }}
            >
              <Icon name={short > 0 ? "alert-triangle" : "check"} size={12} />
              {short > 0 ? `short ${euroCents(short)}` : "payments covered"}
            </span>
          )}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          {m.flexible_budget_cents !== null && m.flexible_funded_cents !== null && (
            <FundingBar label="day-to-day" funded={m.flexible_funded_cents} wanted={m.flexible_budget_cents} />
          )}
          {m.set_aside_wanted_cents !== null && m.set_aside_funded_cents !== null && (
            <FundingBar label="set aside" funded={m.set_aside_funded_cents} wanted={m.set_aside_wanted_cents} />
          )}
          <span style={{ color: "var(--text-subtle)", display: "flex", transform: open ? "rotate(90deg)" : "none", transition: "transform var(--dur-base) var(--ease-out)" }}>
            <Icon name="chevron-right" size={16} />
          </span>
        </span>
      </button>
      {open && (
        <div style={{ paddingBottom: 12 }}>
          {setAsideShort && (
            <p style={{ font: "500 13px/1.45 var(--font-sans)", color: "var(--text-muted)", margin: "0 0 8px" }}>
              This month only {euroCents(m.set_aside_funded_cents ?? 0)} of the {euroCents(m.set_aside_wanted_cents ?? 0)} needed
              for later payments and goals can be set aside. If it keeps happening, something won&apos;t be ready in time —
              adjust the plan.
            </p>
          )}
          {m.occurrences.length === 0 ? (
            <div style={{ font: "500 13.5px var(--font-sans)", color: "var(--text-muted)" }}>No scheduled payments this month.</div>
          ) : (
            m.occurrences.map((o) => (
              <div
                key={o.schedule_id}
                style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "7px 0", borderBottom: "1px dashed var(--border-hairline)", font: "500 14px var(--font-sans)" }}
              >
                <span style={{ display: "flex", gap: 10, alignItems: "center", minWidth: 0 }}>
                  <span style={{ font: "500 12px var(--font-mono)", color: "var(--text-muted)", background: "var(--surface-sunk)", borderRadius: 8, padding: "2px 6px", minWidth: 52, textAlign: "center" }}>
                    {o.day ? `day ${o.day}` : "—"}
                  </span>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {o.category_name} · {o.name}
                  </span>
                </span>
                <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 600, color: "var(--text-strong)" }}>{euroCents(o.amount_cents)}</span>
                  {o.covered === false && (
                    <span style={{ font: "600 12px var(--font-sans)", borderRadius: "var(--r-full)", padding: "2px 8px", background: "var(--warning-soft)", color: "#9A5B00" }}>
                      short {euroCents(o.short_cents ?? 0)}
                    </span>
                  )}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function IncomePrompt() {
  const queryClient = useQueryClient();
  const [value, setValue] = React.useState("");
  const [day, setDay] = React.useState("");
  const cents = parseEuroToCents(value);
  const save = useMutation({
    mutationFn: (c: number) =>
      createIncomeSchedule({
        name: "Monthly income",
        amount_cents: c,
        pattern: "monthly",
        day: day ? Math.min(31, Math.max(1, Number(day))) : null,
      }),
    onSuccess: () => invalidateIncomeQueries(queryClient),
  });
  return (
    <Panel>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (cents !== null && cents > 0) save.mutate(cents);
        }}
        style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}
      >
        <div style={{ flex: "1 1 260px" }}>
          <div style={{ font: "600 15px var(--font-sans)", color: "var(--text-strong)", marginBottom: 4 }}>
            Add your monthly income to see what&apos;s covered
          </div>
          <div style={{ font: "500 13px var(--font-sans)", color: "var(--text-muted)", marginBottom: 10 }}>
            Your fixed take-home pay each month. Bonuses don&apos;t count until they arrive.
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <div style={{ flex: "2 1 180px" }}>
              <Input label="Fixed monthly income" prefix="€" inputMode="decimal" placeholder="0,00" value={value} onChange={(e) => setValue(e.target.value)} />
            </div>
            <div style={{ flex: "1 1 120px" }}>
              <Input
                label="Day it arrives (optional)"
                inputMode="numeric"
                placeholder="—"
                value={day}
                onChange={(e) => setDay(e.target.value.replace(/\D/g, "").slice(0, 2))}
              />
            </div>
          </div>
        </div>
        <Button type="submit" disabled={cents === null || cents <= 0 || save.isPending}>Save income</Button>
      </form>
    </Panel>
  );
}

export default function UpcomingPage() {
  const [month] = useSelectedMonth();
  const upcoming = useQuery({ queryKey: ["upcoming", month], queryFn: () => fetchUpcoming(month) });
  const summary = useQuery({ queryKey: ["plan-summary", month], queryFn: () => fetchPlanSummary(month) });
  const [open, setOpen] = React.useState<string | null>(null);
  const [editingIncome, setEditingIncome] = React.useState(false);

  const s = summary.data;
  const gap = s?.gap_cents ?? null;

  return (
    <>
      <TopBar title="Upcoming payments" sub="If you keep your current plan" />
      <div className="app-content">
        {upcoming.isError || summary.isError ? (
          <ErrorPanel message="We couldn't load your upcoming payments." onRetry={() => { upcoming.refetch(); summary.refetch(); }} />
        ) : !upcoming.data || !s ? (
          <>
            <SkeletonPanel rows={1} rowHeight={96} />
            <SkeletonPanel rows={6} rowHeight={44} />
          </>
        ) : (
          <>
            {!upcoming.data.income_known && <IncomePrompt />}
            <div className="grid-dash-top">
              <SummaryCard
                label="Expected income, next 12 months"
                value={s.income_cents === null ? "—" : euroCents(s.income_cents)}
                note={
                  s.income_known && s.income_cents !== null
                    ? `${euroCents(Math.round(s.income_cents / 12))} a month on average · no bonuses`
                    : "add your monthly income"
                }
                action={
                  <Button variant="secondary" size="sm" onClick={() => setEditingIncome(true)}>
                    Edit income
                  </Button>
                }
              />
              <SummaryCard
                label="Planned costs"
                value={euroCents(s.costs_cents)}
                note={`payments ${euroCents(s.scheduled_cents, 0)} · day-to-day ${euroCents(s.flexible_cents, 0)} · goals ${euroCents(s.goals_cents, 0)}`}
              />
              <SummaryCard
                label={gap === null ? "Gap" : gap >= 0 ? "Left over" : "Short"}
                value={gap === null ? "—" : euroCents(Math.abs(gap))}
                note={gap === null ? "needs your income" : `${euroCents(Math.abs(s.gap_monthly_cents ?? 0))} a month`}
                warn={gap !== null && gap < 0}
              />
            </div>
            <p style={{ font: "500 13.5px/1.5 var(--font-sans)", color: "var(--text-muted)", maxWidth: 720, margin: 0 }}>
              Each month your income goes first to that month&apos;s payments, then to day-to-day, then to setting aside for
              later payments and goals. If a month won&apos;t make it, you see it here ahead of time.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {upcoming.data.months.map((m) => (
                <MonthRow key={m.month} m={m} open={open === m.month} onToggle={() => setOpen(open === m.month ? null : m.month)} />
              ))}
            </div>
          </>
        )}
      </div>
      <IncomeEditorDialog open={editingIncome} onOpenChange={setEditingIncome} />
    </>
  );
}
