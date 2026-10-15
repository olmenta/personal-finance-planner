"use client";

import Link from "next/link";
import React from "react";
import { ProposalCard } from "@/components/coach/ProposalCard";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Panel } from "@/components/ui/Panel";
import type { HomeReason, HomeSummary, HomeView } from "@/lib/api";
import { euroCents } from "@/lib/format";
import { monthLabel } from "@/lib/schedules";

/* Home widgets (spec: home). Every amount comes from GET /home; these
   components only choose words. Statuses are always spelled out in text. */

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

const row: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  gap: 12,
  padding: "9px 0",
  borderBottom: "1px dashed var(--border-hairline)",
  font: "500 14.5px var(--font-sans)",
  color: "var(--text-body)",
};
const amount: React.CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontWeight: 700,
  color: "var(--text-strong)",
  whiteSpace: "nowrap",
};
const muted: React.CSSProperties = { font: "500 13px var(--font-sans)", color: "var(--text-muted)" };

function reasonText(r: HomeReason): string {
  switch (r.code) {
    case "over_assigned":
      return `You've assigned ${euroCents(r.amount_cents)} more than you have`;
    case "overspent_categories":
      return `${plural(r.items.length, "category is", "categories are")} ${euroCents(r.amount_cents)} over`;
    case "unbudgeted_card_spending":
      return `${euroCents(r.amount_cents)} of card spending isn't budgeted`;
    default:
      return `${euroCents(r.amount_cents)} of this month's payments isn't covered yet`;
  }
}

/** One plain sentence with the most important fact (design D7, no greeting). */
export function coachLine(home: HomeView): string {
  if (home.status === "organized") {
    return `Your month is organized. You have ${euroCents(home.summary.left_to_spend_cents)} left to spend.`;
  }
  const by = (code: HomeReason["code"]) => home.reasons.find((r) => r.code === code);
  const uncovered = by("uncovered_payments");
  if (uncovered) return `${euroCents(uncovered.amount_cents)} of this month's payments isn't covered yet. Let's fix that first.`;
  const over = by("overspent_categories");
  if (over) {
    return `${plural(over.items.length, "category needs", "categories need")} money before I can give you a reliable amount to spend.`;
  }
  const assigned = by("over_assigned");
  if (assigned) return `You've assigned ${euroCents(assigned.amount_cents)} more than you have. Let's bring it back before spending more.`;
  const card = by("unbudgeted_card_spending");
  if (card) return `${euroCents(card.amount_cents)} of card spending isn't budgeted yet.`;
  return "Let's organize this month.";
}

export function HomeHeaderLine({ home }: Readonly<{ home: HomeView }>) {
  const updated = new Date(home.generated_at).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  const issues: { text: string; href: string }[] = [];
  if (home.data.pending_import) issues.push({ text: "An import is waiting for your review", href: "/transactions" });
  if (home.data.uncategorized_count > 0) {
    issues.push({
      text: `${plural(home.data.uncategorized_count, "transaction needs", "transactions need")} a category`,
      href: "/transactions",
    });
  }
  if (home.data.limited && !home.data.pending_import && home.data.uncategorized_count === 0) {
    issues.push({
      text: home.data.last_transaction_date
        ? `Nothing recorded since ${new Date(home.data.last_transaction_date).toLocaleDateString("es-ES")}: add or import recent spending`
        : "No transactions yet: add or import your spending",
      href: "/transactions",
    });
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }} data-testid="home-header">
      <div style={muted}>
        {monthLabel(home.month)} · Updated {updated}
        {home.data.last_transaction_date &&
          ` · Last transaction ${new Date(home.data.last_transaction_date).toLocaleDateString("es-ES")}`}
      </div>
      {issues.length > 0 && (
        <div role="status" style={{ display: "flex", flexDirection: "column", gap: 4, background: "var(--warning-soft)", borderRadius: "var(--r-md)", padding: "10px 12px" }}>
          <span style={{ font: "600 13px var(--font-sans)", color: "#8A5300" }}>Review data: these numbers may be incomplete</span>
          {issues.map((i) => (
            <Link key={i.text} href={i.href} style={{ font: "500 13px var(--font-sans)", color: "#8A5300" }}>
              {i.text} →
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function CoachLine({ home }: Readonly<{ home: HomeView }>) {
  return (
    <div data-testid="coach-line" style={{ display: "flex", gap: 10, alignItems: "flex-start", font: "600 16.5px/1.45 var(--font-sans)", color: "var(--text-strong)" }}>
      <Icon name="sparkles" size={18} color="var(--accent)" />
      <span>{coachLine(home)}</span>
    </div>
  );
}

/** M = T + L + F + U, exactly as the server computed it. */
export function Breakdown({ summary: s }: Readonly<{ summary: HomeSummary }>) {
  return (
    <div data-testid="breakdown" style={{ marginTop: 8, background: "var(--surface-sunk)", borderRadius: "var(--r-md)", padding: "10px 12px", font: "500 13.5px/1.7 var(--font-sans)", fontVariantNumeric: "tabular-nums" }}>
      <div><b>Money in your accounts {euroCents(s.accounts_cents)}</b> =</div>
      <div>set aside for this month&apos;s payments {euroCents(s.covered_cents)}</div>
      <div>+ left to spend {euroCents(s.left_to_spend_cents)}</div>
      <div>+ saved for the future {euroCents(s.saved_cents)}</div>
      <div>+ unassigned {euroCents(s.unassigned_cents)}</div>
      <div style={muted}>Paid and card payments already left your accounts, so they&apos;re not part of this sum.</div>
    </div>
  );
}

export function reasonList(reasons: HomeReason[]) {
  return (
    <ul style={{ margin: "6px 0 2px", paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }} data-testid="reasons">
      {reasons.map((r) => (
        <li key={r.code} style={{ font: "500 13.5px var(--font-sans)", color: "var(--text-body)" }}>
          {reasonText(r)}
          {r.items.length > 0 && (
            <span style={muted}>: {r.items.map((i) => `${i.name} ${euroCents(i.amount_cents)}`).join(", ")}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

export interface MonthWidgetProps {
  home: Pick<HomeView, "summary" | "status" | "reasons">;
  /** Start with the exact breakdown expanded ("View how it's split"). */
  breakdownOpen?: boolean;
}

export function MonthWidget({ home, breakdownOpen = false }: Readonly<MonthWidgetProps>) {
  const [open, setOpen] = React.useState(breakdownOpen);
  const s = home.summary;
  const organized = home.status === "organized";
  return (
    <div data-testid="month-widget">
      <Panel title="This month">
      <div style={row}>
        <span>Paid</span>
        <span style={amount}>{euroCents(s.paid_cents)}</span>
      </div>
      {s.card_payments_cents > 0 && (
        <div style={{ ...row, ...muted }}>
          <span>Card payments (purchases already counted)</span>
          <span>{euroCents(s.card_payments_cents)}</span>
        </div>
      )}
      <div style={row}>
        <span>
          Still to pay
          <span style={muted}>
            {" "}
            · {s.short_cents > 0 ? `${euroCents(s.covered_cents)} covered, ${euroCents(s.short_cents)} short` : "all covered"}
          </span>
        </span>
        <span style={amount}>{euroCents(s.still_to_pay_cents)}</span>
      </div>
      <div style={row} data-testid="left-to-spend">
        <span>Left to spend</span>
        {organized ? (
          <span style={amount}>{euroCents(s.left_to_spend_cents)}</span>
        ) : (
          <span style={{ font: "700 13.5px var(--font-sans)", color: "#8A5300" }}>Needs organizing</span>
        )}
      </div>
      {!organized && home.reasons.length > 0 && reasonList(home.reasons)}
      <div style={row}>
        <span>Saved for the future</span>
        <span style={amount}>{euroCents(s.saved_cents)}</span>
      </div>
      <div style={{ ...row, borderBottom: 0 }}>
        <span>Unassigned{s.unassigned_cents < 0 && <span style={muted}> · assigned more than you have</span>}</span>
        <span style={amount}>{euroCents(s.unassigned_cents)}</span>
      </div>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{ border: "none", background: "none", cursor: "pointer", font: "600 13px var(--font-sans)", color: "var(--brand)", padding: "8px 0 0" }}
      >
        {open ? "Hide the breakdown" : "View exact breakdown"}
      </button>
      {open && <Breakdown summary={s} />}
    </Panel>
      </div>
  );
}

export function PriorityAction({ home }: Readonly<{ home: HomeView }>) {
  if (!home.priority) return null;
  return (
    <section aria-label="Do this first" data-testid="priority-action" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div className="ol-eyebrow" style={{ color: "var(--text-subtle)" }}>Do this first</div>
      <ProposalCard key={home.priority.fingerprint} p={home.priority} />
    </section>
  );
}

const VISIBLE_GROUPS = 3;

export function RecommendationGroups({ home }: Readonly<{ home: HomeView }>) {
  const [openKey, setOpenKey] = React.useState<string | null>(null);
  const [showAll, setShowAll] = React.useState(false);
  if (home.groups.length === 0) return null;
  const shown = showAll ? home.groups : home.groups.slice(0, VISIBLE_GROUPS);
  return (
    <section aria-label="Suggestions" data-testid="recommendation-groups" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div className="ol-eyebrow" style={{ color: "var(--text-subtle)" }}>Also worth a look</div>
      {shown.map((g) => {
        const open = openKey === g.key;
        return (
          <div key={g.key} data-testid={`group-${g.key}`} style={{ background: "var(--surface)", borderRadius: "var(--r-lg)", boxShadow: "var(--shadow-sm)", padding: "4px 14px" }}>
            <button
              onClick={() => setOpenKey(open ? null : g.key)}
              aria-expanded={open}
              style={{ width: "100%", border: "none", background: "none", cursor: "pointer", padding: "12px 0", display: "flex", justifyContent: "space-between", font: "600 14.5px var(--font-sans)", color: "var(--text-strong)" }}
            >
              <span>{g.title} ({g.proposals.length})</span>
              <Icon name={open ? "chevron-down" : "chevron-right"} size={16} />
            </button>
            {open && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8, paddingBottom: 12 }}>
                {g.proposals.map((p) => (
                  <ProposalCard key={p.fingerprint} p={p} />
                ))}
              </div>
            )}
          </div>
        );
      })}
      {!showAll && home.groups.length > VISIBLE_GROUPS && (
        <Button variant="ghost" size="sm" onClick={() => setShowAll(true)}>
          See more ({home.groups.length - VISIBLE_GROUPS})
        </Button>
      )}
    </section>
  );
}

/** The Future status in words, with where to act (spec: home). */
export function futureSentence(home: Pick<HomeView, "future">): { lead: string; text: string; link: { href: string; label: string } } {
  const f = home.future;
  if (f.status === "unknown") {
    return {
      lead: "Coverage unknown.",
      text: "Add your expected income to see whether the coming months are covered.",
      link: { href: "/settings#income", label: "Add income" },
    };
  }
  if (f.status === "needs_attention") {
    const parts = [
      f.short_cents > 0 ? `${euroCents(f.short_cents)} of payments won't be covered` : null,
      f.set_aside_gap_cents > 0 ? `${euroCents(f.set_aside_gap_cents)} less is set aside than planned` : null,
    ].filter(Boolean);
    return {
      lead: "Needs attention.",
      text: `From ${f.month ? monthLabel(f.month) : "a coming month"}: ${parts.join(" and ")}. Planning for it now is easier.`,
      link: { href: "/future", label: "Open Future" },
    };
  }
  return {
    lead: "On track.",
    text: "Under your current plan and expected income, the next 12 months' payments are covered.",
    link: { href: "/future", label: "Open Future" },
  };
}

export function FutureWidget({ home }: Readonly<{ home: HomeView }>) {
  const { lead, text, link } = futureSentence(home);
  return (
    <div data-testid="future-widget">
      <Panel title="Future">
      <p style={{ font: "500 14px/1.5 var(--font-sans)", color: "var(--text-body)", margin: "0 0 10px" }}>
        <b>{lead} </b>
        {text}
      </p>
      <Link href={link.href} style={{ textDecoration: "none" }}>
        <Button variant="secondary" size="sm" iconRight="chevron-right">{link.label}</Button>
      </Link>
    </Panel>
      </div>
  );
}

export function NoAccounts() {
  return (
    <div data-testid="no-accounts">
      <Panel>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-start" }}>
        <div style={{ font: "700 17px var(--font-sans)", color: "var(--text-strong)" }}>Start with your accounts</div>
        <div style={{ font: "500 14px/1.5 var(--font-sans)", color: "var(--text-muted)", maxWidth: 520 }}>
          Add the bank accounts, cash and cards you use, with what&apos;s in them today. Then I can tell you what to pay
          and what you can spend.
        </div>
        <Link href="/accounts" style={{ textDecoration: "none" }}>
          <Button iconLeft="plus">Add an account</Button>
        </Link>
      </div>
    </Panel>
      </div>
  );
}
