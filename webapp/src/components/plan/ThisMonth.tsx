"use client";

import Link from "next/link";
import React from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Panel } from "@/components/ui/Panel";
import type { OverviewView, UpcomingMonth } from "@/lib/api";
import { euroCents } from "@/lib/format";
import { monthLabel } from "@/lib/schedules";

/* "Este mes" (spec: month-overview): what to solve now — already paid, still
   to pay (covered or short), left to spend — plus where the rest of the
   money sits. Mirrors the approved prototype's home card. */

const row: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: 10,
  padding: "8px 0",
  borderBottom: "1px dashed var(--border-hairline)",
  font: "500 14px var(--font-sans)",
  color: "var(--text-body)",
};
const amount: React.CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontWeight: 600,
  color: "var(--text-strong)",
  whiteSpace: "nowrap",
};

function DayChip({ day }: Readonly<{ day: number | null }>) {
  return (
    <span
      style={{
        font: "500 12px var(--font-mono)",
        color: "var(--text-muted)",
        background: "var(--surface-sunk)",
        borderRadius: 8,
        padding: "2px 6px",
        minWidth: 52,
        textAlign: "center",
        flex: "none",
      }}
    >
      {day ? `day ${day}` : "this month"}
    </span>
  );
}

function StatusChip({ shortCents }: Readonly<{ shortCents: number }>) {
  const ok = shortCents <= 0;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        font: "600 12px var(--font-sans)",
        borderRadius: "var(--r-full)",
        padding: "2px 8px",
        whiteSpace: "nowrap",
        background: ok ? "var(--mint-50)" : "var(--warning-soft)",
        color: ok ? "var(--mint-700)" : "#9A5B00",
      }}
    >
      <Icon name={ok ? "check" : "alert-triangle"} size={12} />
      {ok ? "set aside" : `short ${euroCents(shortCents)}`}
    </span>
  );
}

function Section({
  icon,
  title,
  total,
  big,
  children,
}: Readonly<{ icon: string; title: string; total: number; big?: boolean; children: React.ReactNode }>) {
  return (
    <div style={{ padding: "6px 0 10px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, padding: "8px 0 4px" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 8, font: "600 15px var(--font-sans)", color: "var(--text-strong)" }}>
          <Icon name={icon} size={18} /> {title}
        </span>
        <span
          style={{
            font: `${big ? 800 : 700} ${big ? 26 : 18}px var(--font-sans)`,
            letterSpacing: big ? "-0.8px" : "-0.4px",
            color: "var(--text-strong)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {euroCents(total)}
        </span>
      </div>
      {children}
    </div>
  );
}

export function ThisMonthPanel({ overview }: Readonly<{ overview: OverviewView }>) {
  const [showPaid, setShowPaid] = React.useState(false);
  const leftNet = overview.left_to_spend.total_cents;
  return (
    <Panel title={`${monthLabel(overview.month)} · what to solve now`}>
      <Section icon="check-circle" title="Already paid this month" total={overview.paid.total_cents}>
        <button
          onClick={() => setShowPaid((s) => !s)}
          aria-expanded={showPaid}
          style={{ border: "none", background: "none", cursor: "pointer", font: "500 13px var(--font-sans)", color: "var(--text-muted)", padding: 0 }}
        >
          {showPaid ? "Hide payments and spending" : "See payments and spending"}
        </button>
        {showPaid && (
          <div>
            {overview.paid.items.map((p, i) => (
              <div key={`${p.category_id}-${i}`} style={row}>
                <span style={{ display: "flex", gap: 10, alignItems: "center", minWidth: 0 }}>
                  <DayChip day={p.day} />
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {p.name ? `${p.category_name} · ${p.name}` : p.category_name}
                  </span>
                </span>
                <span style={amount}>{euroCents(p.amount_cents)}</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section icon="calendar" title="Still to pay this month" total={overview.to_pay_total_cents}>
        {overview.to_pay.length === 0 ? (
          <div style={{ ...row, borderBottom: 0, color: "var(--text-muted)" }}>No scheduled payments left this month.</div>
        ) : (
          overview.to_pay.map((p) => (
            <div key={p.schedule_id} style={row}>
              <span style={{ display: "flex", gap: 10, alignItems: "center", minWidth: 0 }}>
                <DayChip day={p.day} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {p.category_name} · {p.name}
                </span>
              </span>
              <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={amount}>{euroCents(p.amount_cents)}</span>
                <StatusChip shortCents={p.short_cents} />
              </span>
            </div>
          ))
        )}
      </Section>

      <Section icon="wallet" title="Left to spend" total={leftNet - overview.overspent_cents} big>
        {overview.left_to_spend.items.length === 0 ? (
          <div style={{ ...row, borderBottom: 0, color: "var(--text-muted)" }}>
            Give your day-to-day categories an amount on Budgets to see what&apos;s left here.
          </div>
        ) : (
          overview.left_to_spend.items.map((c) => (
            <div key={c.category_id} style={row}>
              <span>{c.name}</span>
              <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>
                  spent {euroCents(c.spent_cents ?? 0)}
                </span>
                <span style={{ ...amount, color: c.amount_cents < 0 ? "var(--expense)" : amount.color }}>
                  {euroCents(c.amount_cents)}
                </span>
              </span>
            </div>
          ))
        )}
      </Section>
    </Panel>
  );
}

export function ThisMonthSide({
  overview,
  next,
}: Readonly<{ overview: OverviewView; next: UpcomingMonth[] }>) {
  const groups = new Map<string, { name: string; amount: number }[]>();
  for (const s of overview.saved.items) {
    groups.set(s.group, [...(groups.get(s.group) ?? []), { name: s.name, amount: s.amount_cents }]);
  }
  const left = overview.left_to_spend.total_cents - overview.overspent_cents;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Panel title="Saved for the future">
        <div style={{ font: "800 24px var(--font-sans)", letterSpacing: "-0.7px", color: "var(--text-strong)", fontVariantNumeric: "tabular-nums" }}>
          {euroCents(overview.saved.total_cents)}
        </div>
        <div style={{ font: "500 13px var(--font-sans)", color: "var(--text-muted)", margin: "4px 0 10px", lineHeight: 1.45 }}>
          Money in your accounts that already has a job: next months&apos; payments, goals and savings. Not for today.
        </div>
        {[...groups].map(([group, items]) => (
          <div key={group} style={{ marginBottom: 10 }}>
            <div className="ol-eyebrow" style={{ color: "var(--text-subtle)", marginBottom: 4 }}>{group}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {items.map((i) => (
                <span key={i.name} style={{ font: "500 12.5px var(--font-sans)", background: "var(--surface-sunk)", borderRadius: "var(--r-full)", padding: "3px 10px" }}>
                  {i.name} <b style={{ fontVariantNumeric: "tabular-nums", color: "var(--text-strong)" }}>{euroCents(i.amount)}</b>
                </span>
              ))}
            </div>
          </div>
        ))}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderTop: "1px solid var(--border-hairline)", paddingTop: 12, marginTop: 4 }}>
          <span style={{ font: "600 15px var(--font-sans)", color: "var(--text-strong)" }}>Unassigned</span>
          <span style={{ font: "700 18px var(--font-sans)", color: "var(--text-strong)", fontVariantNumeric: "tabular-nums" }}>
            {euroCents(overview.to_be_assigned_cents)}
          </span>
        </div>
        <div style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
          {overview.to_be_assigned_cents > 0
            ? "Give it a job on Budgets — if not, it carries to next month."
            : "Every euro has a job."}
        </div>
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "flex-start",
            marginTop: 12,
            background: "var(--surface-sunk)",
            borderRadius: "var(--r-md)",
            padding: "10px 12px",
            font: "500 12.5px/1.45 var(--font-sans)",
            color: "var(--text-muted)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          <Icon name="landmark" size={15} />
          <span>
            In your accounts: <b style={{ color: "var(--text-strong)" }}>{euroCents(overview.accounts_cents)}</b> = to pay{" "}
            {euroCents(overview.covered_cents)} + to spend {euroCents(left)} + saved {euroCents(overview.saved.total_cents)} +
            unassigned {euroCents(overview.to_be_assigned_cents)}
          </span>
        </div>
      </Panel>

      <Panel
        title="Next months"
        action={
          <Link href="/upcoming">
            <Button variant="ghost" size="sm" iconRight="chevron-right">See all</Button>
          </Link>
        }
      >
        {next.length === 0 ? (
          <div style={{ font: "500 13.5px var(--font-sans)", color: "var(--text-muted)" }}>
            Set up your payments to see what&apos;s coming.
          </div>
        ) : (
          next.map((m) => (
            <div key={m.month} style={row}>
              <b style={{ color: "var(--text-strong)" }}>{monthLabel(m.month)}</b>
              <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={amount}>{euroCents(m.payments_cents)}</span>
                {m.short_cents === null ? null : <StatusChip shortCents={m.short_cents} />}
              </span>
            </div>
          ))
        )}
      </Panel>
      <Link href="/debts" style={{ textDecoration: "none" }}>
        <Button variant="secondary" size="sm" iconLeft="landmark" iconRight="chevron-right" block>
          What you owe
        </Button>
      </Link>
    </div>
  );
}
