"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/shadcn/dialog";
import { PayeeField } from "@/components/PayeeField";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  ApiError,
  createIncomeSchedule,
  deleteIncomeSchedule,
  fetchIncomeSchedules,
  fetchPayees,
  updateIncomeSchedule,
  type IncomeScheduleIn,
  type IncomeScheduleOut,
} from "@/lib/api";
import { euroCents, money, parseEuroToCents } from "@/lib/format";
import { invalidateIncomeQueries } from "@/lib/planQueries";
import { describe } from "@/lib/schedules";
import { useSelectedMonth } from "@/lib/selectedMonth";
import {
  ScheduleRuleFields,
  ruleBody,
  ruleDay,
  ruleDraftFrom,
  type RuleDraft,
} from "./ScheduleRuleFields";

/* Income editor (spec: income-schedules): each fixed income described once —
   amount, rule, day and payer. Feeds the plan and expected-versus-received;
   never the budget (principle 1). */

const EXTRA_PAY_MONTHS = [6, 12];

interface Draft extends RuleDraft {
  id: string | null; // null = new income
  name: string;
  amount: string;
  payer: string;
}

function toDraft(s: IncomeScheduleOut | null, month: string): Draft {
  return {
    ...ruleDraftFrom(s, month, EXTRA_PAY_MONTHS),
    id: s?.id ?? null,
    name: s?.name ?? "",
    amount: s ? money(s.amount_cents / 100) : "",
    payer: s?.payer ?? "",
  };
}

function toBody(d: Draft): IncomeScheduleIn | null {
  const amount = parseEuroToCents(d.amount);
  const rule = ruleBody(d);
  if (!d.name.trim() || amount === null || amount <= 0 || !rule || rule.pattern === "no_date") return null;
  return {
    ...rule,
    name: d.name.trim(),
    amount_cents: amount,
    day: ruleDay(d),
    estimated: d.estimated,
    payer: d.payer.trim(),
  };
}

const sentence = (s: IncomeScheduleIn | IncomeScheduleOut) =>
  describe(s) + (s.payer ? ` · ${s.payer}` : "");

export function IncomeEditor() {
  const [month] = useSelectedMonth();
  const queryClient = useQueryClient();
  const { data: schedules, isPending } = useQuery({
    queryKey: ["income-schedules"],
    queryFn: fetchIncomeSchedules,
  });
  const { data: payees = [] } = useQuery({ queryKey: ["payees"], queryFn: fetchPayees });
  const list = schedules ?? [];
  const [draft, setDraft] = React.useState<Draft>(() => toDraft(null, month));
  const [error, setError] = React.useState<string | null>(null);

  const refresh = () => {
    invalidateIncomeQueries(queryClient);
    // The payer may be a new payee.
    queryClient.invalidateQueries({ queryKey: ["payees"] });
  };
  const onError = (e: unknown) =>
    setError(
      e instanceof ApiError && e.code === "invalid_schedule"
        ? "Some fields don't fit this kind of income — check them and try again."
        : "That didn't save — try again.",
    );

  const save = useMutation({
    mutationFn: (body: IncomeScheduleIn) =>
      draft.id ? updateIncomeSchedule(draft.id, body) : createIncomeSchedule(body),
    onSuccess: () => {
      setDraft(toDraft(null, month));
      setError(null);
      refresh();
    },
    onError,
  });
  const addExtraPays = useMutation({
    mutationFn: async (body: IncomeScheduleIn) => {
      await createIncomeSchedule(body);
      await createIncomeSchedule({
        name: "Paga extra",
        amount_cents: body.amount_cents,
        pattern: "some_months",
        months: EXTRA_PAY_MONTHS,
        day: body.day,
        payer: body.payer,
      });
    },
    onSuccess: () => {
      setDraft(toDraft(null, month));
      setError(null);
      refresh();
    },
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteIncomeSchedule(id),
    onSuccess: () => {
      setDraft(toDraft(null, month));
      refresh();
    },
    onError,
  });

  const body = toBody(draft);
  const yearly = list.reduce((t, s) => t + s.yearly_cents, 0);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const canAddExtraPays = !draft.id && body?.pattern === "monthly" && !body.count;

  return (
    <div className="grid-2" style={{ gap: 20, alignItems: "start" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ background: "var(--surface-sunk)", borderRadius: "var(--r-md)", padding: "12px 14px" }}>
          <div className="ol-eyebrow" style={{ color: "var(--text-muted)" }}>Expected, next 12 months</div>
          <div
            style={{ font: "700 22px var(--font-sans)", letterSpacing: "-0.5px", color: "var(--text-strong)", fontVariantNumeric: "tabular-nums", marginTop: 4 }}
            data-testid="income-yearly"
          >
            {euroCents(yearly)}
          </div>
          <div style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
            {euroCents(Math.round(yearly / 12))} a month on average · bonuses count when they arrive
          </div>
        </div>
        {!isPending && list.length === 0 && (
          <div style={{ font: "500 14px var(--font-sans)", color: "var(--text-muted)", padding: "4px 2px" }}>
            Add your income to see if your plan fits.
          </div>
        )}
        {list.map((s) => (
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
            }}
          >
            <span style={{ font: "600 14px var(--font-sans)", color: "var(--text-strong)", display: "block" }}>{s.name}</span>
            <span style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>{sentence(s)}</span>
          </button>
        ))}
        {list.length > 0 && (
          <div>
            <Button variant="secondary" size="sm" iconLeft="plus" onClick={() => setDraft(toDraft(null, month))}>
              Add income
            </Button>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (body) save.mutate(body);
        }}
        style={{ display: "flex", flexDirection: "column", gap: 14, background: "var(--surface-sunk)", borderRadius: "var(--r-lg)", padding: 16 }}
        aria-label="Income form"
      >
        <div style={{ font: "600 16px/1.5 var(--font-sans)", color: "var(--text-strong)", minHeight: 24 }}>
          {body ? sentence(body) : "New income"}
        </div>
        <Input label="Name" placeholder="Nómina" value={draft.name} onChange={(e) => set("name", e.target.value)} />
        <PayeeField
          label="Payer"
          value={draft.payer}
          payees={payees}
          onChange={(v) => set("payer", v)}
          onPick={(p) => set("payer", p.name)}
        />
        <ScheduleRuleFields
          draft={draft}
          onChange={(k, v) => setDraft((d) => ({ ...d, [k]: v }))}
          month={month}
          allowNoDate={false}
          labels={{
            pattern: "How often it arrives",
            months: "Months it arrives",
            next: "Next one",
            count: "Number of payments (empty = no end)",
            estimated: "The amount varies",
            estimatedHint: "Freelance or variable pay: an amount close to it counts as received",
          }}
          amountField={
            <Input
              label="Net amount each time"
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
              Remove income
            </Button>
          ) : canAddExtraPays ? (
            <Button
              type="button"
              variant="secondary"
              disabled={addExtraPays.isPending}
              onClick={() => body && addExtraPays.mutate(body)}
            >
              14 payments a year
            </Button>
          ) : (
            <span />
          )}
          <Button type="submit" disabled={!body || save.isPending}>
            {draft.id ? "Save income" : "Add income"}
          </Button>
        </div>
      </form>
    </div>
  );
}

export function IncomeEditorDialog({
  open,
  onOpenChange,
}: Readonly<{ open: boolean; onOpenChange: (open: boolean) => void }>) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="p-0 gap-0 overflow-hidden"
        style={{
          borderRadius: "var(--r-2xl)",
          maxWidth: 820,
          width: "calc(100vw - 32px)",
          maxHeight: "calc(100vh - 48px)",
          overflowY: "auto",
          border: "1px solid var(--border-hairline)",
          boxShadow: "var(--shadow-xl)",
        }}
      >
        <DialogHeader style={{ padding: "20px 24px 14px", borderBottom: "1px solid var(--border-hairline)" }}>
          <DialogTitle style={{ font: "700 19px var(--font-sans)", letterSpacing: "-0.4px", color: "var(--text-strong)" }}>
            Your income
          </DialogTitle>
          <div style={{ marginTop: 6, font: "500 13.5px var(--font-sans)", color: "var(--text-muted)" }}>
            What you expect to receive and when. Your budget only uses income once it arrives.
          </div>
        </DialogHeader>
        <div style={{ padding: 20 }}>
          <IncomeEditor />
        </div>
      </DialogContent>
    </Dialog>
  );
}
