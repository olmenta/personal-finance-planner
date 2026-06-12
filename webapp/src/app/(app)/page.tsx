"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React from "react";
import { useQuery } from "@tanstack/react-query";
import { AddTransactionDialog } from "@/components/AddTransactionDialog";
import { BalanceCard } from "@/components/ui/BalanceCard";
import { Badge } from "@/components/ui/Badge";
import { BudgetBar } from "@/components/ui/BudgetBar";
import { Button } from "@/components/ui/Button";
import { CoachCapsule } from "@/components/ui/CoachCapsule";
import { Icon } from "@/components/ui/Icon";
import { Panel } from "@/components/ui/Panel";
import { ErrorPanel, SkeletonPanel } from "@/components/ui/QueryStates";
import { StatCard } from "@/components/ui/StatCard";
import { TransactionRow } from "@/components/ui/TransactionRow";
import { TopBar } from "@/components/shell/TopBar";
import {
  currentMonth,
  fetchBudgetMonth,
  fetchCategories,
  fetchOnboardingStatus,
  fetchSummary,
  fetchTransactions,
  toneForCategory,
  type CategoryOut,
  type SummaryView,
  type TransactionOut,
} from "@/lib/api";
import { euroCents, splitEuro } from "@/lib/format";

function SpendChart({ summary }: Readonly<{ summary: SummaryView }>) {
  const max = Math.max(
    1,
    ...summary.weeks.flatMap((w) => [w.spent_cents, w.income_cents]),
  );
  return (
    <Panel
      title="Spending this month"
      action={
        <div style={{ display: "flex", gap: 14 }}>
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              font: "500 12px var(--font-sans)",
              color: "var(--text-muted)",
            }}
          >
            <span style={{ width: 10, height: 10, borderRadius: 3, background: "var(--violet-500)" }} />{" "}
            Spent
          </span>
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              font: "500 12px var(--font-sans)",
              color: "var(--text-muted)",
            }}
          >
            <span style={{ width: 10, height: 10, borderRadius: 3, background: "var(--mint-400)" }} />{" "}
            Income
          </span>
        </div>
      }
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 18,
          height: 180,
          padding: "0 4px",
        }}
      >
        {summary.weeks.map((w, i) => (
          <div
            key={w.start}
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 10,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                gap: 6,
                height: 150,
                width: "100%",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  width: 14,
                  height: `${Math.round((w.spent_cents / max) * 100)}%`,
                  background: "var(--grad-balance)",
                  borderRadius: "6px 6px 3px 3px",
                }}
              />
              <div
                style={{
                  width: 14,
                  height: `${Math.round((w.income_cents / max) * 100)}%`,
                  background: "var(--mint-300)",
                  borderRadius: "6px 6px 3px 3px",
                }}
              />
            </div>
            <span style={{ font: "600 12px var(--font-sans)", color: "var(--text-subtle)" }}>
              W{i + 1}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* Spent share of the bar's limit; >100 reads as over even with no limit. */
function spentPercent(spentCents: number, limitCents: number): number {
  if (limitCents > 0) return Math.round((spentCents / limitCents) * 100);
  return spentCents > 0 ? 101 : 0;
}

function RecentTransactions({
  rows,
  categories,
}: Readonly<{ rows: TransactionOut[]; categories: Map<string, CategoryOut> }>) {
  if (rows.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "26px 0 10px" }}>
        <div style={{ font: "600 15px var(--font-sans)", color: "var(--text-strong)" }}>
          Nothing here yet — add your first transaction
        </div>
        <div style={{ font: "500 13px var(--font-sans)", color: "var(--text-muted)", marginTop: 6 }}>
          Every euro you track makes your budget smarter.
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {rows.map((t, i) => {
        const category = t.category_id ? categories.get(t.category_id) : undefined;
        const isIncome = t.amount_cents > 0;
        return (
          <div
            key={t.id}
            style={{
              borderBottom: i < rows.length - 1 ? "1px solid var(--border-hairline)" : "none",
            }}
          >
            <TransactionRow
              icon={isIncome ? "dollar-sign" : (category?.icon ?? "circle")}
              tone={isIncome ? "income" : toneForCategory(category?.icon ?? "circle")}
              title={t.description ?? category?.name ?? "Transaction"}
              subtitle={`${category?.name ?? "Uncategorized"} · ${t.date.slice(8)}/${t.date.slice(5, 7)}`}
              amount={euroCents(Math.abs(t.amount_cents))}
              direction={isIncome ? "in" : "out"}
              card={false}
            />
          </div>
        );
      })}
    </div>
  );
}

const ONBOARDING_DISMISSED_KEY = "olmenta-onboarding-nudge-dismissed";

/* Dismissible entry point to the AI onboarding interview, shown until the
   user has a completed session (spec: ai-onboarding, dashboard entry point). */
function OnboardingNudge() {
  const router = useRouter();
  // Lazy init instead of an effect: rendering is gated on statusQuery.data,
  // which only resolves client-side, so SSR/hydration both render null.
  const [dismissed, setDismissed] = React.useState(
    () =>
      typeof localStorage !== "undefined" &&
      localStorage.getItem(ONBOARDING_DISMISSED_KEY) === "1",
  );
  const statusQuery = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: fetchOnboardingStatus,
  });

  if (dismissed || !statusQuery.data || statusQuery.data.has_completed) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
      <CoachCapsule
        message={
          statusQuery.data.has_active
            ? "Your setup interview is waiting — pick up where you left off"
            : "Finish setting up — a 2-minute chat builds your budget"
        }
        cta={statusQuery.data.has_active ? "Resume" : "Start"}
        accent="violet"
        onClick={() => router.push("/onboarding")}
        style={{ flex: 1 }}
      />
      <button
        aria-label="Dismiss"
        onClick={() => {
          globalThis.localStorage.setItem(ONBOARDING_DISMISSED_KEY, "1");
          setDismissed(true);
        }}
        style={{
          border: "none",
          background: "transparent",
          cursor: "pointer",
          color: "var(--text-subtle)",
          padding: 6,
        }}
      >
        <Icon name="x" size={16} />
      </button>
    </div>
  );
}

export default function OverviewPage() {
  const month = currentMonth();
  const summaryQuery = useQuery({
    queryKey: ["summary", month],
    queryFn: () => fetchSummary(month),
  });
  const budgetQuery = useQuery({
    queryKey: ["budget", month],
    queryFn: () => fetchBudgetMonth(month),
  });
  const txQuery = useQuery({
    queryKey: ["transactions", month],
    queryFn: () => fetchTransactions(month),
  });
  const catQuery = useQuery({ queryKey: ["categories"], queryFn: fetchCategories });

  const categories = React.useMemo(() => {
    const map = new Map<string, CategoryOut>();
    for (const g of catQuery.data ?? []) {
      for (const c of g.categories) map.set(c.id, c);
    }
    return map;
  }, [catQuery.data]);

  /* Budgets panel: top categories by spent; limit = assigned + rollover. */
  const topBudgets = React.useMemo(() => {
    const cats = (budgetQuery.data?.groups ?? []).flatMap((g) => g.categories);
    return cats
      .filter((c) => c.spent_cents > 0 || c.assigned_cents + c.rollover_cents > 0)
      .sort((a, b) => b.spent_cents - a.spent_cents)
      .slice(0, 4);
  }, [budgetQuery.data]);
  const activeCount = (budgetQuery.data?.groups ?? [])
    .flatMap((g) => g.categories)
    .filter((c) => c.spent_cents > 0 || c.assigned_cents + c.rollover_cents > 0).length;

  const summary = summaryQuery.data;
  const net = summary ? summary.income_cents - summary.expense_cents : 0;
  const [balanceAmount, balanceCents] = summary ? splitEuro(summary.balance_cents) : ["", ""];

  if (summaryQuery.isError) {
    return (
      <>
        <TopBar title="Overview" sub="Welcome back" />
        <div className="app-content">
          <ErrorPanel
            message="We couldn't load your overview."
            onRetry={() => summaryQuery.refetch()}
          />
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar title="Overview" sub="Welcome back" />
      <div className="app-content">
        <OnboardingNudge />
        {summary ? (
          <div className="grid-dash-top">
            <BalanceCard
              label="Current balance"
              amount={balanceAmount}
              cents={balanceCents}
              align="left"
              delta={
                <>
                  <Icon name={net >= 0 ? "trending-up" : "trending-down"} size={15} />{" "}
                  {net >= 0 ? "+" : "−"}
                  {euroCents(Math.abs(net))} this month
                </>
              }
              style={{ borderRadius: "var(--r-xl)" }}
            />
            <StatCard
              icon="trending-up"
              tone="income"
              label="Income"
              value={euroCents(summary.income_cents)}
            />
            <StatCard
              icon="trending-down"
              tone="expense"
              label="Expenses"
              value={euroCents(summary.expense_cents)}
            />
          </div>
        ) : (
          <SkeletonPanel rows={1} rowHeight={120} />
        )}

        {/* The web reference keeps coach insights in the rail; the capsule
            appears only when the rail is collapsed (<1440px). */}
        <div className="coach-capsule-fallback">
          <CoachCapsule message="You're spending 18% more on dining this month" cta="See why" />
        </div>

        <div className="grid-dash-mid">
          {summary ? <SpendChart summary={summary} /> : <SkeletonPanel rows={3} rowHeight={52} />}
          {budgetQuery.data ? (
            <Panel
              title="Budgets"
              action={<Badge tone="brand">{activeCount} active</Badge>}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 17 }}>
                {topBudgets.map((c) => {
                  const limit = c.assigned_cents + c.rollover_cents;
                  return (
                    <BudgetBar
                      key={c.id}
                      icon={c.icon}
                      tone={toneForCategory(c.icon)}
                      label={c.name}
                      spent={euroCents(c.spent_cents, 0)}
                      limit={euroCents(limit, 0)}
                      percent={spentPercent(c.spent_cents, limit)}
                    />
                  );
                })}
              </div>
            </Panel>
          ) : (
            <SkeletonPanel rows={4} rowHeight={40} />
          )}
        </div>

        {txQuery.data && catQuery.data ? (
          <Panel
            title="Recent transactions"
            action={
              <div style={{ display: "flex", gap: 8 }}>
                <AddTransactionDialog>
                  <Button variant="primary" size="sm" iconLeft="plus">
                    Add transaction
                  </Button>
                </AddTransactionDialog>
                <Link href="/transactions">
                  <Button variant="ghost" size="sm" iconRight="chevron-right">
                    View all
                  </Button>
                </Link>
              </div>
            }
          >
            <RecentTransactions rows={txQuery.data.slice(0, 4)} categories={categories} />
          </Panel>
        ) : (
          <SkeletonPanel rows={4} rowHeight={48} />
        )}
      </div>
    </>
  );
}
