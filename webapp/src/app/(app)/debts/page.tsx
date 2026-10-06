"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DebtEditor } from "@/components/debts/DebtEditor";
import { TopBar } from "@/components/shell/TopBar";
import { Button } from "@/components/ui/Button";
import { IconChip } from "@/components/ui/IconChip";
import { Input } from "@/components/ui/Input";
import { Panel } from "@/components/ui/Panel";
import { ErrorPanel, SkeletonPanel } from "@/components/ui/QueryStates";
import {
  deleteDebt,
  fetchDebts,
  putDebtExtra,
  type DebtOut,
  type DebtsView,
} from "@/lib/api";
import { rateLabel } from "@/lib/debts";
import { euroCents, money, parseEuroToCents } from "@/lib/format";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { monthLabel } from "@/lib/schedules";

/* What you owe (spec: debts): the total, the debt-free month, the debts in
   the order to pay them (highest interest first) and the monthly extra.
   Plain words only — no TAE, APR or amortization. */

const KIND_ICON: Record<DebtOut["kind"], string> = {
  card: "credit-card",
  loan: "landmark",
  personal: "users",
};

function requiredLine(d: DebtOut): string {
  if (d.kind === "card") {
    return d.plan_monthly_cents ? `${euroCents(d.plan_monthly_cents)} a month` : "no monthly plan yet";
  }
  if (d.kind === "loan") {
    const left = d.installments_left ?? 0;
    return `${euroCents(d.installment_cents ?? 0)} a month · ${left} ${left === 1 ? "installment" : "installments"} left`;
  }
  return d.due_month ? `due ${monthLabel(d.due_month)}` : "whenever you can";
}

function endLine(d: DebtOut): string {
  if (d.end_month) return `done in ${monthLabel(d.end_month)}`;
  return d.kind === "personal" && !d.due_month
    ? "paid from the extra once the others are done"
    : "no end in sight at this pace";
}

/** Why the first debt goes first, in one sentence. */
function firstReason(d: DebtOut, debts: DebtOut[]): string {
  const withRate = debts.filter((x) => !x.paid_off && x.monthly_rate_bp != null);
  if (d.monthly_rate_bp != null && withRate.length > 1) return "Pay this one first: it charges you the most.";
  if (d.monthly_rate_bp != null) return "Pay this one first: it's the one charging you interest.";
  return "Pay this one first: it's the closest to done.";
}

function DebtRow({
  d,
  debts,
  extraTarget,
  extra,
  onWork,
}: Readonly<{ d: DebtOut; debts: DebtOut[]; extraTarget: boolean; extra: number; onWork: () => void }>) {
  const queryClient = useQueryClient();
  const removePlan = useMutation({
    mutationFn: () => deleteDebt(d.id),
    onSuccess: () => invalidateMoneyQueries(queryClient),
  });
  return (
    <div
      data-testid={`debt-row-${d.name}`}
      style={{
        background: "var(--surface)",
        borderRadius: "var(--r-lg)",
        boxShadow: "var(--shadow-sm)",
        padding: "14px 16px",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ font: "700 13px var(--font-sans)", color: "var(--text-subtle)", minWidth: 18 }}>
          {d.position ?? "✓"}
        </span>
        <IconChip icon={KIND_ICON[d.kind]} tone={d.paid_off ? "mint" : "violet"} size={34} />
        <div style={{ flex: "1 1 200px", minWidth: 0 }}>
          <div style={{ font: "600 15px var(--font-sans)", color: "var(--text-strong)" }}>{d.name}</div>
          <div style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
            {d.paid_off ? "Paid off" : `${requiredLine(d)} · ${endLine(d)} · ${rateLabel(d.rate_bp, d.rate_period)}`}
          </div>
        </div>
        <div style={{ font: "700 17px var(--font-sans)", letterSpacing: "-0.3px", color: "var(--text-strong)", fontVariantNumeric: "tabular-nums" }}>
          {euroCents(d.owed_cents)}
        </div>
        <Button variant="secondary" size="sm" onClick={onWork}>Work on my debts</Button>
      </div>
      {d.position === 1 && (
        <div style={{ font: "500 13.5px/1.45 var(--font-sans)", color: "var(--text-body)", paddingLeft: 30 }}>
          {firstReason(d, debts)}
          {d.monthly_interest_cents ? ` ~${euroCents(d.monthly_interest_cents)}/month just for owing it.` : ""}
          {extraTarget && extra > 0 ? ` Your extra ${euroCents(extra)} goes here this month.` : ""}
        </div>
      )}
      {d.below_minimum && (
        <div style={{ font: "500 13px var(--font-sans)", color: "#8A5300", paddingLeft: 30 }}>
          Your plan is below what the bank asks for — that usually means a fee and more interest.
        </div>
      )}
      {d.paid_off && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, paddingLeft: 30, flexWrap: "wrap" }}>
          <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--mint-700)" }}>
            Done — one less thing to carry.
          </span>
          <Button variant="ghost" size="sm" onClick={() => removePlan.mutate()} disabled={removePlan.isPending}>
            Remove the plan
          </Button>
        </div>
      )}
    </div>
  );
}

function ExtraPanel({ data }: Readonly<{ data: DebtsView }>) {
  const queryClient = useQueryClient();
  const [value, setValue] = React.useState(() => money(data.extra_monthly_cents / 100));
  const cents = parseEuroToCents(value);
  const save = useMutation({
    mutationFn: (c: number) => putDebtExtra(c),
    onSuccess: () => invalidateMoneyQueries(queryClient),
  });
  const { suggested_cents: suggested, saved_cents: saved } = data.cushion;
  return (
    <Panel>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (cents !== null && cents >= 0) save.mutate(cents);
        }}
        style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}
      >
        <div style={{ flex: "1 1 240px" }}>
          <div style={{ font: "600 15px var(--font-sans)", color: "var(--text-strong)", marginBottom: 4 }}>
            Extra for your debts each month
          </div>
          <div style={{ font: "500 13px var(--font-sans)", color: "var(--text-muted)", marginBottom: 10 }}>
            Optional. It all goes to the first one in the list; when that one is done, the next one gets it.
          </div>
          <Input label="Extra a month" prefix="€" inputMode="decimal" placeholder="0,00" value={value}
            onChange={(e) => setValue(e.target.value)} />
        </div>
        <Button type="submit" disabled={cents === null || cents < 0 || save.isPending}>Save extra</Button>
      </form>
      {data.extra_monthly_cents > 0 && saved < suggested && (
        <p data-testid="cushion-note" style={{ font: "500 13.5px/1.5 var(--font-sans)", color: "var(--text-body)", background: "var(--mint-50)", borderRadius: "var(--r-md)", padding: "10px 12px", margin: "12px 0 0" }}>
          Before the extra, try to keep about {euroCents(suggested)} saved for surprises
          {saved > 0 ? ` (you have ${euroCents(saved)})` : ""} — so the next unexpected bill doesn&apos;t end up back
          on the card.
        </p>
      )}
    </Panel>
  );
}

export default function DebtsPage() {
  const query = useQuery({ queryKey: ["debts"], queryFn: fetchDebts });
  const [editing, setEditing] = React.useState<{ open: boolean; debt: DebtOut | null }>({ open: false, debt: null });
  const data = query.data;
  const open = (debt: DebtOut | null) => setEditing({ open: true, debt });
  const active = (data?.debts ?? []).filter((d) => !d.paid_off);

  return (
    <>
      <TopBar title="What you owe" sub="A plan to pay it off, starting with the one that costs you most" />
      <div className="app-content">
        {/* Always visible: the entry point to work on any debt (spec: debts). */}
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button iconLeft="plus" onClick={() => open(null)} data-testid="work-on-debts">
            Work on my debts
          </Button>
        </div>
        {query.isError ? (
          <ErrorPanel message="We couldn't load what you owe." onRetry={() => query.refetch()} />
        ) : !data ? (
          <SkeletonPanel rows={4} rowHeight={56} />
        ) : data.debts.length === 0 ? (
          <Panel>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-start" }}>
              <div style={{ font: "700 17px var(--font-sans)", color: "var(--text-strong)" }}>List what you owe</div>
              <div style={{ font: "500 14px/1.5 var(--font-sans)", color: "var(--text-muted)", maxWidth: 520 }}>
                Cards, loans with installments, money a friend lent you. You&apos;ll get the order to pay them in and
                the month you&apos;ll be free of them.
              </div>
            </div>
          </Panel>
        ) : (
          <>
            <Panel>
              <div className="ol-eyebrow" style={{ color: "var(--text-subtle)" }}>What you owe</div>
              <div data-testid="debts-total" style={{ font: "800 30px var(--font-sans)", letterSpacing: "-0.9px", color: "var(--text-strong)", fontVariantNumeric: "tabular-nums", marginTop: 6 }}>
                {euroCents(data.total_owed_cents)}
              </div>
              <div data-testid="debt-free" style={{ font: "500 14px var(--font-sans)", color: "var(--text-muted)", marginTop: 2 }}>
                {active.length === 0
                  ? "Nothing left to pay — well done."
                  : data.debt_free_month
                    ? `Debt-free in ${monthLabel(data.debt_free_month)} if you keep this plan`
                    : "Add an extra or a date to the debts without one to see when you'll be done"}
              </div>
            </Panel>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {data.debts.map((d) => (
                <DebtRow
                  key={d.id}
                  d={d}
                  debts={data.debts}
                  extraTarget={data.extra_target_debt_id === d.id}
                  extra={data.extra_monthly_cents}
                  onWork={() => open(d)}
                />
              ))}
            </div>
            <ExtraPanel key={data.extra_monthly_cents} data={data} />
          </>
        )}
      </div>
      <DebtEditor
        open={editing.open}
        onOpenChange={(o) => setEditing((s) => ({ ...s, open: o }))}
        debt={editing.debt}
      />
    </>
  );
}
