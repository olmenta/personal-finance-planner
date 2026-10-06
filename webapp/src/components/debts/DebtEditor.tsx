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
import { useAccounts } from "@/components/AccountPicker";
import { PayeeField } from "@/components/PayeeField";
import { Field, triggerStyle } from "@/components/plan/ScheduleRuleFields";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Switch } from "@/components/ui/Switch";
import {
  ApiError,
  createDebt,
  currentMonth,
  deleteDebt,
  fetchPayees,
  updateDebt,
  type DebtIn,
  type DebtKind,
  type DebtOut,
  type DebtUpdate,
  type RatePeriod,
} from "@/lib/api";
import { monthlyRate, paymentsToPayOff, planForTarget } from "@/lib/debts";
import { euroCents, money, parseEuroToCents } from "@/lib/format";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { monthFromIndex, monthIndex, monthLabel } from "@/lib/schedules";

/* Debt plan editor (spec: debts): a few plain questions per kind. The
   "Work on my debts" button opens it; the chat follow-up will open the coach
   interview instead (proposal, Next). */

const KINDS: { value: DebtKind; label: string }[] = [
  { value: "card", label: "A card" },
  { value: "loan", label: "A loan with installments" },
  { value: "personal", label: "Money I owe someone" },
];

type RateChoice = RatePeriod | "unknown";

interface Draft {
  kind: DebtKind;
  // card
  accountId: string;
  planMode: "amount" | "date";
  plan: string;
  targetMonth: string;
  minimum: string;
  // loan
  name: string;
  installment: string;
  left: string;
  nextMonth: string;
  day: string;
  // personal
  lender: string;
  owed: string;
  hasDate: boolean;
  dueMonth: string;
  // rate
  rate: string;
  ratePeriod: RateChoice;
}

const cents = (v: string) => parseEuroToCents(v);
const euros = (c: number | null | undefined) => (c ? money(c / 100) : "");

function toDraft(debt: DebtOut | null, kind: DebtKind): Draft {
  const month = currentMonth();
  const next = monthFromIndex(monthIndex(month) + 1);
  return {
    kind: debt?.kind ?? kind,
    accountId: debt?.account_id ?? "",
    planMode: "amount",
    plan: euros(debt?.plan_monthly_cents),
    targetMonth: monthFromIndex(monthIndex(month) + 5),
    minimum: euros(debt?.minimum_cents),
    name: debt?.kind === "card" ? "" : (debt?.name ?? ""),
    installment: euros(debt?.installment_cents),
    left: debt?.installments_left ? String(debt.installments_left) : "",
    nextMonth: debt?.next_month ?? month,
    day: debt?.day ? String(debt.day) : "",
    lender: debt?.lender ?? "",
    owed: euros(debt?.kind === "personal" ? debt.owed_cents : null),
    hasDate: !!debt?.due_month,
    dueMonth: debt?.due_month ?? next,
    rate: debt?.rate_bp != null ? (debt.rate_bp / 100).toLocaleString("es-ES") : "",
    ratePeriod: debt?.rate_period ?? "unknown",
  };
}

function rateFields(d: Draft): { rate_bp: number | null; rate_period: RatePeriod | null } {
  const pct = Number(d.rate.replace(",", "."));
  if (d.ratePeriod === "unknown" || !d.rate.trim() || !Number.isFinite(pct) || pct < 0) {
    return { rate_bp: null, rate_period: null };
  }
  return { rate_bp: Math.round(pct * 100), rate_period: d.ratePeriod };
}

const monthChoices = (count = 36) =>
  Array.from({ length: count }, (_, k) => monthFromIndex(monthIndex(currentMonth()) + k));

function MonthPicker({ label, value, onChange }: Readonly<{ label: string; value: string; onChange: (v: string) => void }>) {
  return (
    <Field label={label}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="h-11 rounded-[10px] border-[1.5px] text-sm font-medium" style={triggerStyle}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {monthChoices().map((m) => (
            <SelectItem key={m} value={m}>{monthLabel(m)}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}

/* A labelled group of buttons: a <label> would name its first button. */
function Group({ label, children }: Readonly<{ label: string; children: React.ReactNode }>) {
  return (
    <div role="group" aria-label={label} style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-body)" }}>{label}</span>
      {children}
    </div>
  );
}

const note: React.CSSProperties = {
  font: "500 13px/1.45 var(--font-sans)",
  color: "var(--text-muted)",
  background: "var(--surface-sunk)",
  borderRadius: "var(--r-md)",
  padding: "10px 12px",
};

export interface DebtEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null = add a new debt. */
  debt: DebtOut | null;
}

export function DebtEditor({ open, onOpenChange, debt }: Readonly<DebtEditorProps>) {
  const queryClient = useQueryClient();
  const { active: accounts } = useAccounts(open);
  const cards = accounts.filter((a) => a.type === "credit");
  const { data: payees = [] } = useQuery({ queryKey: ["payees"], queryFn: fetchPayees, enabled: open });
  const [draft, setDraft] = React.useState<Draft>(() => toDraft(debt, "card"));
  const [error, setError] = React.useState<string | null>(null);

  // Reset each time the editor opens on a (different) debt.
  const [seededFor, setSeededFor] = React.useState<string | null>(null);
  const seedKey = open ? (debt?.id ?? "new") : null;
  if (seedKey !== seededFor) {
    setSeededFor(seedKey);
    setDraft(toDraft(debt, "card"));
    setError(null);
  }
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));

  const done = () => {
    invalidateMoneyQueries(queryClient);
    queryClient.invalidateQueries({ queryKey: ["categories"] });
    queryClient.invalidateQueries({ queryKey: ["payees"] });
    onOpenChange(false);
  };
  const onError = (e: unknown) =>
    setError(
      e instanceof ApiError && e.code === "debt_exists"
        ? "That one already has a plan — open it from the list to change it."
        : "Some details don't add up — check them and try again.",
    );
  const save = useMutation({
    mutationFn: (payload: { create?: DebtIn; update?: DebtUpdate }) =>
      payload.create ? createDebt(payload.create) : updateDebt(debt!.id, payload.update!),
    onSuccess: done,
    onError,
  });
  const remove = useMutation({ mutationFn: () => deleteDebt(debt!.id), onSuccess: done, onError });

  // Live preview of the card plan.
  const rate = (() => {
    const r = rateFields(draft);
    return monthlyRate(r.rate_bp, r.rate_period);
  })();
  const account = cards.find((a) => a.id === draft.accountId);
  const cardOwed = debt?.kind === "card" ? debt.owed_cents : (account?.uncovered_debt_cents ?? 0);
  const months = monthIndex(draft.targetMonth) - monthIndex(currentMonth()) + 1;
  const planCents =
    draft.planMode === "amount" ? (cents(draft.plan) ?? 0) : planForTarget(cardOwed, rate, months);
  const payments = draft.planMode === "amount" ? paymentsToPayOff(cardOwed, rate, planCents) : months;
  const minimumCents = cents(draft.minimum);
  const belowMinimum = draft.kind === "card" && minimumCents !== null && planCents > 0 && planCents < minimumCents;

  function payload(): { create?: DebtIn; update?: DebtUpdate } | null {
    const r = rateFields(draft);
    const day = draft.day ? Math.min(31, Math.max(1, Number(draft.day))) : null;
    if (draft.kind === "card") {
      if (!draft.accountId && !debt) return null;
      const amount = cents(draft.plan) ?? 0;
      if (draft.planMode === "amount" && amount <= 0) return null;
      const plan = draft.planMode === "amount" ? { plan_monthly_cents: amount } : { target_month: draft.targetMonth };
      const minimum = minimumCents && minimumCents > 0 ? minimumCents : undefined;
      if (debt) return { update: { ...r, ...plan, minimum_cents: minimum ?? null } };
      return { create: { kind: "card", account_id: draft.accountId, ...r, ...plan, minimum_cents: minimum } };
    }
    if (draft.kind === "loan") {
      const installment = cents(draft.installment);
      const left = Number(draft.left);
      if (!draft.name.trim() || !installment || installment <= 0 || !(left >= 1)) return null;
      const fields = { installment_cents: installment, installments_left: left, next_month: draft.nextMonth, day };
      if (debt) return { update: { ...r, ...fields, name: draft.name.trim() } };
      return { create: { kind: "loan", name: draft.name.trim(), ...r, ...fields } };
    }
    const owed = cents(draft.owed);
    if (!draft.name.trim() || !owed || owed <= 0) return null;
    const fields = {
      owed_cents: owed,
      due_month: draft.hasDate ? draft.dueMonth : null,
      lender: draft.lender.trim() || null,
    };
    if (debt) return { update: { ...r, ...fields, name: draft.name.trim() } };
    return { create: { kind: "personal", name: draft.name.trim(), ...r, ...fields } };
  }
  const body = payload();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="p-0 gap-0 overflow-hidden"
        style={{
          borderRadius: "var(--r-2xl)",
          maxWidth: 520,
          width: "calc(100vw - 32px)",
          maxHeight: "calc(100vh - 48px)",
          overflowY: "auto",
          border: "1px solid var(--border-hairline)",
          boxShadow: "var(--shadow-xl)",
        }}
      >
        <DialogHeader style={{ padding: "20px 24px 14px", borderBottom: "1px solid var(--border-hairline)" }}>
          <DialogTitle style={{ font: "700 19px var(--font-sans)", letterSpacing: "-0.4px", color: "var(--text-strong)" }}>
            {debt ? `Your plan · ${debt.name}` : "Add something you owe"}
          </DialogTitle>
        </DialogHeader>
        <form
          aria-label="Debt plan"
          onSubmit={(e) => {
            e.preventDefault();
            if (body) save.mutate(body);
          }}
          style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}
        >
          {!debt && (
            <Group label="What is it?">
              <SegmentedControl
                size="sm"
                options={KINDS}
                value={draft.kind}
                onChange={(v) => set("kind", v as DebtKind)}
              />
            </Group>
          )}

          {draft.kind === "card" && (
            <>
              {!debt && (
                <Field label="Which card?">
                  <Select value={draft.accountId} onValueChange={(v) => set("accountId", v)}>
                    <SelectTrigger className="h-11 rounded-[10px] border-[1.5px] text-sm font-medium" style={triggerStyle} aria-label="Which card?">
                      <SelectValue placeholder={cards.length ? "Pick a card" : "Add a card in Accounts first"} />
                    </SelectTrigger>
                    <SelectContent>
                      {cards.map((a) => (
                        <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              )}
              {(debt || account) && (
                <div style={{ font: "500 13.5px var(--font-sans)", color: "var(--text-muted)" }}>
                  You owe <b style={{ color: "var(--text-strong)" }}>{euroCents(cardOwed)}</b> on it, not counting
                  what&apos;s already set aside for new purchases.
                </div>
              )}
              <SegmentedControl
                size="sm"
                options={[
                  { value: "amount", label: "How much a month?" },
                  { value: "date", label: "When do you want to be done?" },
                ]}
                value={draft.planMode}
                onChange={(v) => set("planMode", v as Draft["planMode"])}
              />
              {draft.planMode === "amount" ? (
                <Input label="How much can you pay a month?" prefix="€" inputMode="decimal" placeholder="0,00"
                  value={draft.plan} onChange={(e) => set("plan", e.target.value)} />
              ) : (
                <MonthPicker label="When do you want to be done?" value={draft.targetMonth} onChange={(v) => set("targetMonth", v)} />
              )}
              {cardOwed > 0 && planCents > 0 && (
                <div style={note} data-testid="card-plan-preview">
                  {draft.planMode === "amount"
                    ? payments === null
                      ? "At that pace the interest eats the payment — try a bit more."
                      : `Done in ${monthLabel(monthFromIndex(monthIndex(currentMonth()) + payments - 1))}.`
                    : `That's ${euroCents(planCents)} a month.`}
                </div>
              )}
              <Input label="What's the least the bank lets you pay? (optional)" prefix="€" inputMode="decimal"
                placeholder="Skip if you don't know" value={draft.minimum} onChange={(e) => set("minimum", e.target.value)} />
              {belowMinimum && (
                <div role="alert" style={{ ...note, background: "var(--warning-soft)", color: "#8A5300" }}>
                  The bank asks for at least {euroCents(minimumCents!)}. Paying less usually means a late fee and more
                  interest — aim for at least that.
                </div>
              )}
            </>
          )}

          {draft.kind === "loan" && (
            <>
              <Input label="Name" placeholder="Préstamo BBVA" value={draft.name} onChange={(e) => set("name", e.target.value)} />
              <div className="grid-2">
                <Input label="Each installment" prefix="€" inputMode="decimal" placeholder="0,00"
                  value={draft.installment} onChange={(e) => set("installment", e.target.value)} />
                <Input label="Installments left" inputMode="numeric" placeholder="12"
                  value={draft.left} onChange={(e) => set("left", e.target.value.replace(/\D/g, ""))} />
              </div>
              <div className="grid-2">
                <MonthPicker label="Next one" value={draft.nextMonth} onChange={(v) => set("nextMonth", v)} />
                <Input label="Day of the month (optional)" inputMode="numeric" placeholder="—"
                  value={draft.day} onChange={(e) => set("day", e.target.value.replace(/\D/g, "").slice(0, 2))} />
              </div>
            </>
          )}

          {draft.kind === "personal" && (
            <>
              <Input label="Name" placeholder="Jose y Ruby" value={draft.name} onChange={(e) => set("name", e.target.value)} />
              <PayeeField label="Who lent it to you? (optional)" value={draft.lender} payees={payees}
                onChange={(v) => set("lender", v)} onPick={(p) => set("lender", p.name)} />
              <Input label="How much do you owe?" prefix="€" inputMode="decimal" placeholder="0,00"
                value={draft.owed} onChange={(e) => set("owed", e.target.value)} />
              <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-body)" }}>
                  Do they need it back by a date?
                  <span style={{ display: "block", font: "500 12px var(--font-sans)", color: "var(--text-muted)" }}>
                    With a date, it&apos;s set aside a bit every month until then
                  </span>
                </span>
                <Switch checked={draft.hasDate} onChange={(v) => set("hasDate", v)} />
              </label>
              {draft.hasDate && (
                <MonthPicker label="By when?" value={draft.dueMonth} onChange={(v) => set("dueMonth", v)} />
              )}
            </>
          )}

          <Group label="How much does it charge you?">
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              {draft.ratePeriod !== "unknown" && (
                <div style={{ width: 120 }}>
                  <Input aria-label="Interest" inputMode="decimal" placeholder="1,5" value={draft.rate}
                    onChange={(e) => set("rate", e.target.value)} />
                </div>
              )}
              <SegmentedControl
                size="sm"
                options={[
                  { value: "month", label: "% a month" },
                  { value: "year", label: "% a year" },
                  { value: "unknown", label: "I don't know" },
                ]}
                value={draft.ratePeriod}
                onChange={(v) => set("ratePeriod", v as RateChoice)}
              />
            </div>
          </Group>

          {error && (
            <div role="alert" style={{ font: "600 13px var(--font-sans)", color: "var(--expense)", background: "var(--expense-soft)", borderRadius: "var(--r-md)", padding: "9px 12px" }}>
              {error}
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
            {debt ? (
              <Button type="button" variant="ghost" onClick={() => remove.mutate()} disabled={remove.isPending}>
                Remove this debt
              </Button>
            ) : (
              <span />
            )}
            <Button type="submit" disabled={!body || save.isPending}>
              {debt ? "Save plan" : "Add to my plan"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
