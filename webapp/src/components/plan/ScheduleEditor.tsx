"use client";

import Link from "next/link";
import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/shadcn/dialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  ApiError,
  createSchedule,
  deleteSchedule,
  fetchSchedules,
  updateSchedule,
  type ScheduleIn,
  type ScheduleOut,
} from "@/lib/api";
import { euroCents, money, parseEuroToCents } from "@/lib/format";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import {
  MONTH_SHORT,
  balanceProjection,
  catchUp,
  categoryNormal,
  describe,
  monthLabel,
  normalAmount,
} from "@/lib/schedules";
import {
  ScheduleRuleFields,
  ruleBody,
  ruleDay,
  ruleDraftFrom,
  type RuleDraft,
} from "./ScheduleRuleFields";

export interface ScheduleEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categoryId: string;
  categoryName: string;
  /** Month the amounts are computed for (the month on screen). */
  month: string;
  /** What the category already holds at the start of `month` (rollover). */
  savedCents: number;
}

interface Draft extends RuleDraft {
  id: string | null; // null = new payment
  name: string;
  amount: string;
}

function toDraft(s: ScheduleOut | null, month: string): Draft {
  return {
    ...ruleDraftFrom(s, month),
    id: s?.id ?? null,
    name: s?.name ?? "",
    amount: s ? money(s.amount_cents / 100) : "",
  };
}

function toBody(d: Draft): ScheduleIn | null {
  const amount = parseEuroToCents(d.amount);
  const rule = ruleBody(d);
  if (!d.name.trim() || amount === null || amount <= 0 || !rule) return null;
  if (rule.pattern === "no_date") return { name: d.name.trim(), amount_cents: amount, pattern: "no_date" };
  return { ...rule, name: d.name.trim(), amount_cents: amount, day: ruleDay(d), estimated: d.estimated };
}

function AmountCard({
  label,
  cents,
  note,
  highlight,
}: Readonly<{ label: string; cents: number; note: string; highlight?: boolean }>) {
  return (
    <div
      style={{
        background: highlight ? "var(--warning-soft)" : "var(--surface-sunk)",
        borderRadius: "var(--r-md)",
        padding: "12px 14px",
      }}
    >
      <div className="ol-eyebrow" style={{ color: "var(--text-muted)" }}>{label}</div>
      <div
        style={{
          font: "700 19px var(--font-sans)",
          letterSpacing: "-0.4px",
          color: "var(--text-strong)",
          fontVariantNumeric: "tabular-nums",
          marginTop: 4,
        }}
      >
        {euroCents(cents)}
      </div>
      <div style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>{note}</div>
    </div>
  );
}

function BalanceChart({ points }: Readonly<{ points: ReturnType<typeof balanceProjection> }>) {
  const W = 520;
  const H = 170;
  const pad = 22;
  const values = points.flatMap((p) => [p.normal, p.suggested]).concat(0);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const y = (v: number) => pad + ((max - v) / span) * (H - pad * 2);
  const y0 = y(0);
  const bw = (W - pad * 2) / points.length;
  return (
    <svg viewBox={`0 0 ${W} ${H + 18}`} style={{ width: "100%", height: "auto", display: "block" }} role="img"
      aria-label="Projected balance of the category, month by month">
      <line x1={pad} x2={W - pad} y1={y0} y2={y0} stroke="var(--border-hairline)" />
      {points.map((p, i) => {
        const x = pad + i * bw;
        return (
          <g key={p.month}>
            {[p.normal, p.suggested].map((v, k) => (
              <rect
                key={k}
                x={x + 4 + k * (bw / 2 - 3)}
                y={Math.min(y(v), y0)}
                width={bw / 2 - 6}
                height={Math.max(1, Math.abs(y(v) - y0))}
                rx={3}
                fill={v < -50 ? "var(--warning)" : k === 0 ? "var(--chart-3)" : "var(--chart-1)"}
              >
                <title>{`${monthLabel(p.month)}: ${euroCents(Math.round(v))}`}</title>
              </rect>
            ))}
            {p.payment > 0 && (
              <circle cx={x + bw / 2} cy={pad - 10} r={4} fill="var(--text-strong)">
                <title>{`Payment of ${euroCents(p.payment)} in ${monthLabel(p.month)}`}</title>
              </circle>
            )}
            <text x={x + bw / 2} y={H + 12} textAnchor="middle" fontSize={11} fill="var(--text-muted)"
              fontFamily="var(--font-sans)">
              {MONTH_SHORT[Number(p.month.slice(5, 7)) - 1]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* Schedule editor (spec: payment-schedules): describe a payment once and the
   app computes the monthly amount. Mirrors the prototype's "Configurar pagos". */
export function ScheduleEditor({
  open,
  onOpenChange,
  categoryId,
  categoryName,
  month,
  savedCents,
}: Readonly<ScheduleEditorProps>) {
  const queryClient = useQueryClient();
  const queryKey = ["schedules", categoryId];
  const { data: schedules = [] } = useQuery({
    queryKey,
    queryFn: () => fetchSchedules(categoryId),
    enabled: open,
  });
  const [draft, setDraft] = React.useState<Draft>(() => toDraft(null, month));
  const [error, setError] = React.useState<string | null>(null);

  // Select the first payment when the list arrives; a new draft otherwise.
  const [seededFor, setSeededFor] = React.useState<string | null>(null);
  const seedKey = open ? `${categoryId}:${schedules.length > 0}` : null;
  if (seedKey !== seededFor) {
    setSeededFor(seedKey);
    setDraft(toDraft(schedules[0] ?? null, month));
    setError(null);
  }

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey });
    invalidateMoneyQueries(queryClient);
  };
  const onError = (e: unknown) =>
    setError(
      e instanceof ApiError && e.code === "invalid_schedule"
        ? "Some fields don't fit this kind of payment — check them and try again."
        : "That didn't save — try again.",
    );

  const save = useMutation({
    mutationFn: (body: ScheduleIn) =>
      draft.id ? updateSchedule(draft.id, body) : createSchedule(categoryId, body),
    onSuccess: (saved) => {
      setDraft(toDraft(saved, month));
      setError(null);
      refresh();
    },
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteSchedule(id),
    onSuccess: () => {
      setDraft(toDraft(null, month));
      refresh();
    },
    onError,
  });

  // Debt payments are written from "What you owe" only (spec: payment-schedules).
  const managedByDebt = schedules.some((s) => s.debt_id);
  const body = toBody(draft);
  // Live preview: saved list with the draft in place of (or added to) its row.
  const preview: (ScheduleIn | ScheduleOut)[] = [
    ...schedules.filter((s) => s.id !== draft.id),
    ...(body ? [body] : []),
  ];
  const normal = categoryNormal(preview, month);
  const needed = catchUp(preview, month, savedCents);
  const behind = needed > normal + 0.5;
  const points = balanceProjection(preview, month, savedCents);
  const worst = points.reduce((w, p) => (p.normal < w.normal ? p : w), points[0]);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="p-0 gap-0 overflow-hidden"
        style={{
          borderRadius: "var(--r-2xl)",
          maxWidth: 920,
          width: "calc(100vw - 32px)",
          maxHeight: "calc(100vh - 48px)",
          overflowY: "auto",
          border: "1px solid var(--border-hairline)",
          boxShadow: "var(--shadow-xl)",
        }}
      >
        <DialogHeader style={{ padding: "20px 24px 14px", borderBottom: "1px solid var(--border-hairline)" }}>
          <DialogTitle style={{ font: "700 19px var(--font-sans)", letterSpacing: "-0.4px", color: "var(--text-strong)" }}>
            Payments · {categoryName}
          </DialogTitle>
          <div style={{ marginTop: 6, font: "500 13.5px var(--font-sans)", color: "var(--text-muted)" }}>
            Each payment has its own rule. The category sets aside the sum of their monthly amounts:{" "}
            <b style={{ color: "var(--text-strong)", fontVariantNumeric: "tabular-nums" }}>
              {euroCents(Math.ceil(Math.max(normal, needed) - 1e-9))}/month
            </b>
          </div>
        </DialogHeader>

        <div className="grid-dash-mid" style={{ padding: 20, gap: 20 }}>
          {/* Left: payments + amounts */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {schedules.length === 0 && (
                <div style={{ font: "500 14px var(--font-sans)", color: "var(--text-muted)", padding: "6px 2px" }}>
                  Describe a payment once — the monthly amount is worked out for you.
                </div>
              )}
              {schedules.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setDraft(toDraft(s, month))}
                  aria-pressed={draft.id === s.id}
                  style={{
                    textAlign: "left",
                    border: "none",
                    cursor: "pointer",
                    borderRadius: "var(--r-md)",
                    padding: "9px 12px",
                    background: draft.id === s.id ? "var(--violet-50)" : "transparent",
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 10,
                  }}
                >
                  <span style={{ minWidth: 0 }}>
                    <span style={{ font: "600 14px var(--font-sans)", color: "var(--text-strong)", display: "block" }}>
                      {s.name}
                    </span>
                    <span style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>{describe(s)}</span>
                  </span>
                  <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-strong)", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
                    {euroCents(Math.round(normalAmount(s, month)))}
                    <span style={{ color: "var(--text-subtle)", fontWeight: 500 }}>/mo</span>
                  </span>
                </button>
              ))}
              <div>
                {!managedByDebt && (
                  <Button variant="secondary" size="sm" iconLeft="plus" onClick={() => setDraft(toDraft(null, month))}>
                    Add payment
                  </Button>
                )}
              </div>
            </div>

            <div className="grid-2">
              <AmountCard label="Normal amount" cents={Math.round(normal)} note="cost of the year ÷ 12" />
              <AmountCard
                label="To be on time"
                cents={Math.ceil(Math.max(normal, needed) - 1e-9)}
                note={behind ? "You're behind — set this aside this month" : "You're on track — the normal amount is enough"}
                highlight={behind}
              />
            </div>
            <div style={{ font: "500 13px var(--font-sans)", color: "var(--text-muted)", lineHeight: 1.5 }}>
              {worst && worst.normal < -50
                ? `With the normal amount you'd be ${euroCents(Math.round(-worst.normal))} short in ${monthLabel(worst.month)}. Setting aside the "to be on time" amount covers every payment, and it drops back to normal once you catch up.`
                : "With the normal amount every payment is covered."}
            </div>
            <div>
              <div style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-strong)", marginBottom: 6 }}>
                Category balance, month by month
              </div>
              <BalanceChart points={points} />
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap", font: "500 12px var(--font-sans)", color: "var(--text-muted)", marginTop: 6 }}>
                <span><i style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: "var(--chart-3)", marginRight: 5 }} />Normal amount</span>
                <span><i style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: "var(--chart-1)", marginRight: 5 }} />To be on time</span>
                <span><i style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: "var(--warning)", marginRight: 5 }} />Would fall short</span>
              </div>
            </div>
          </div>

          {/* Right: sentence-style form (debt payments: read-only) */}
          {managedByDebt ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, background: "var(--surface-sunk)", borderRadius: "var(--r-lg)", padding: 16 }}>
              <div style={{ font: "600 15px var(--font-sans)", color: "var(--text-strong)" }}>Managed from What you owe</div>
              <div style={{ font: "500 13.5px/1.5 var(--font-sans)", color: "var(--text-muted)" }}>
                This is a debt payment. Change it from your debt plan so the order and the end date stay right.
              </div>
              <div>
                <Link href="/debts"><Button variant="secondary" size="sm" iconRight="chevron-right">Open What you owe</Button></Link>
              </div>
            </div>
          ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (body) save.mutate(body);
            }}
            style={{ display: "flex", flexDirection: "column", gap: 14, background: "var(--surface-sunk)", borderRadius: "var(--r-lg)", padding: 16 }}
          >
            <div style={{ font: "600 16px/1.5 var(--font-sans)", color: "var(--text-strong)", minHeight: 24 }}>
              {body ? describe(body) : "New payment"}
            </div>
            <Input label="Name" placeholder="School fee" value={draft.name} onChange={(e) => set("name", e.target.value)} />
            <ScheduleRuleFields
              draft={draft}
              onChange={(k, v) => setDraft((d) => ({ ...d, [k]: v }))}
              month={month}
              amountField={
                <Input
                  label={draft.pattern === "no_date" ? "Goal for the year" : "Amount of each payment"}
                  prefix="€"
                  inputMode="decimal"
                  placeholder="0,00"
                  value={draft.amount}
                  onChange={(e) => set("amount", e.target.value)}
                />
              }
            />

            {error && (
              <div role="alert" style={{ font: "600 13px var(--font-sans)", color: "var(--expense)", background: "var(--expense-soft)", borderRadius: "var(--r-md)", padding: "9px 12px" }}>
                {error}
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
              {draft.id ? (
                <Button type="button" variant="ghost" onClick={() => draft.id && remove.mutate(draft.id)}>
                  Remove payment
                </Button>
              ) : (
                <span />
              )}
              <Button type="submit" disabled={!body || save.isPending}>
                {draft.id ? "Save payment" : "Add payment"}
              </Button>
            </div>
          </form>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
