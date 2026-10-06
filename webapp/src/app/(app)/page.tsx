"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React from "react";
import { useSelectedMonth } from "@/lib/selectedMonth";
import { useQuery } from "@tanstack/react-query";
import { AddTransactionDialog } from "@/components/AddTransactionDialog";
import { Button } from "@/components/ui/Button";
import { CoachCapsule } from "@/components/ui/CoachCapsule";
import { Icon } from "@/components/ui/Icon";
import { Panel } from "@/components/ui/Panel";
import { ErrorPanel, SkeletonPanel } from "@/components/ui/QueryStates";
import { TransactionRow } from "@/components/ui/TransactionRow";
import { transferTitle, useAccounts } from "@/components/AccountPicker";
import { TopBar } from "@/components/shell/TopBar";
import { LateIncomeNudge } from "@/components/plan/LateIncomeNudge";
import { ThisMonthPanel, ThisMonthSide } from "@/components/plan/ThisMonth";
import {
  fetchCategories,
  fetchOnboardingStatus,
  fetchOverview,
  fetchSummary,
  fetchTransactions,
  fetchUpcoming,
  toneForCategory,
  type AccountOut,
  type CategoryOut,
  type SummaryView,
  type TransactionOut,
} from "@/lib/api";
import { euroCents } from "@/lib/format";

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

function RecentTransactions({
  rows,
  categories,
  accounts,
}: Readonly<{
  rows: TransactionOut[];
  categories: Map<string, CategoryOut>;
  accounts: AccountOut[];
}>) {
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
        const isTransfer = t.transfer_pair_id !== null;
        const isIncome = t.amount_cents > 0;
        const day = `${t.date.slice(8)}/${t.date.slice(5, 7)}`;
        if (isTransfer) {
          return (
            <div
              key={t.id}
              style={{
                borderBottom: i < rows.length - 1 ? "1px solid var(--border-hairline)" : "none",
              }}
            >
              <TransactionRow
                icon="arrow-left-right"
                tone="neutral"
                title={transferTitle(t, accounts)}
                subtitle={t.description ? `${t.description} · ${day}` : day}
                amount={`${isIncome ? "+" : "−"}${euroCents(Math.abs(t.amount_cents))}`}
                direction="none"
                card={false}
              />
            </div>
          );
        }
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
  const [month] = useSelectedMonth();
  const summaryQuery = useQuery({
    queryKey: ["summary", month],
    queryFn: () => fetchSummary(month),
  });
  const overviewQuery = useQuery({
    queryKey: ["overview", month],
    queryFn: () => fetchOverview(month),
  });
  const upcomingQuery = useQuery({
    queryKey: ["upcoming", month],
    queryFn: () => fetchUpcoming(month),
  });
  const txQuery = useQuery({
    queryKey: ["transactions", month],
    queryFn: () => fetchTransactions(month),
  });
  const catQuery = useQuery({ queryKey: ["categories"], queryFn: fetchCategories });
  const { all: accounts } = useAccounts();

  const categories = React.useMemo(() => {
    const map = new Map<string, CategoryOut>();
    for (const g of catQuery.data ?? []) {
      for (const c of g.categories) map.set(c.id, c);
    }
    return map;
  }, [catQuery.data]);

  const summary = summaryQuery.data;
  const overview = overviewQuery.data;
  const nextMonths = (upcomingQuery.data?.months ?? []).slice(1, 4);

  if (overviewQuery.isError) {
    return (
      <>
        <TopBar title="Overview" sub="Welcome back" />
        <div className="app-content">
          <ErrorPanel
            message="We couldn't load your overview."
            onRetry={() => overviewQuery.refetch()}
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
        {/* Lateness is about today's month, whatever month is on screen. */}
        {overview && <LateIncomeNudge month={overview.today.slice(0, 7)} />}
        {overview ? (
          <div className="grid-dash-mid">
            <ThisMonthPanel overview={overview} />
            <ThisMonthSide overview={overview} next={nextMonths} />
          </div>
        ) : (
          <div className="grid-dash-mid">
            <SkeletonPanel rows={6} rowHeight={40} />
            <SkeletonPanel rows={4} rowHeight={40} />
          </div>
        )}

        {/* The web reference keeps coach insights in the rail; the capsule
            appears only when the rail is collapsed (<1440px). */}
        <div className="coach-capsule-fallback">
          <CoachCapsule message="You're spending 18% more on dining this month" cta="See why" />
        </div>

        {summary ? <SpendChart summary={summary} /> : <SkeletonPanel rows={3} rowHeight={52} />}

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
            <RecentTransactions rows={txQuery.data.slice(0, 4)} categories={categories} accounts={accounts} />
          </Panel>
        ) : (
          <SkeletonPanel rows={4} rowHeight={48} />
        )}
      </div>
    </>
  );
}
