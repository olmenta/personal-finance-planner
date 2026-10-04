"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { BudgetBar } from "@/components/ui/BudgetBar";
import { Button } from "@/components/ui/Button";
import { CoachCapsule } from "@/components/ui/CoachCapsule";
import { IconButton } from "@/components/ui/IconButton";
import { Panel } from "@/components/ui/Panel";
import { ErrorPanel, SkeletonPanel } from "@/components/ui/QueryStates";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { TbaHero } from "@/components/ui/TbaHero";
import { AssignGroups } from "@/components/budget/AssignGroups";
import { IncomeBreakdown } from "@/components/budget/IncomeBreakdown";
import { MoveMoneySheet } from "@/components/budget/MoveMoneySheet";
import { ScheduleEditor } from "@/components/plan/ScheduleEditor";
import { TopBar } from "@/components/shell/TopBar";
import { euroCents } from "@/lib/format";
import type { BudgetCategoryView, BudgetGroupView } from "@/lib/api";
import { useBudgetMonth } from "@/lib/useBudgetMonth";
import { budgets, chartLegend } from "@/lib/mock-data";

/* ---- Report mode (the pre-existing spending view, kept as-is) ---- */

function Donut() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "8px 0 4px",
      }}
    >
      <div
        style={{
          position: "relative",
          width: 210,
          height: 210,
          borderRadius: "50%",
          background:
            "conic-gradient(var(--chart-1) 0 31%, var(--chart-3) 31% 55%, var(--chart-2) 55% 76%, var(--chart-4) 76% 90%, var(--chart-empty) 90% 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            width: 132,
            height: 132,
            background: "var(--surface)",
            borderRadius: "50%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span style={{ font: "500 12px var(--font-sans)", color: "var(--text-muted)" }}>
            Total expenses
          </span>
          <span
            style={{
              font: "800 24px var(--font-sans)",
              letterSpacing: "-0.8px",
              color: "var(--text-strong)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            4.212 €
          </span>
        </div>
        <span
          style={{
            position: "absolute",
            top: 18,
            right: 4,
            background: "var(--ink-900)",
            color: "#fff",
            font: "700 12px var(--font-mono)",
            padding: "5px 10px",
            borderRadius: 999,
          }}
        >
          31%
        </span>
      </div>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          justifyContent: "center",
          margin: "18px 0 4px",
        }}
      >
        {chartLegend.map(([c, l]) => (
          <span
            key={l}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              font: "500 12px var(--font-sans)",
              color: "var(--text-muted)",
            }}
          >
            <span style={{ width: 10, height: 10, borderRadius: 3, background: c }} /> {l}
          </span>
        ))}
      </div>
    </div>
  );
}

function ReportMode() {
  return (
    <div className="grid-dash-mid">
      <Panel title="Expenses report">
        <Donut />
      </Panel>
      <Panel title="By category" action={<Badge tone="brand">4 categories</Badge>}>
        <div style={{ display: "flex", flexDirection: "column", gap: 17 }}>
          {budgets.map((c) => (
            <BudgetBar key={c.label} {...c} />
          ))}
        </div>
      </Panel>
    </div>
  );
}

/* ---- Assign mode (zero-based assignment surface) ---- */

function FirstMonthEmptyState() {
  return (
    <Panel style={{ textAlign: "center", padding: 40 }}>
      <div
        style={{
          font: "700 18px var(--font-sans)",
          letterSpacing: "-0.3px",
          color: "var(--text-strong)",
        }}
      >
        No earlier months yet — assign your first euro
      </div>
      <div
        style={{
          font: "500 14px var(--font-sans)",
          color: "var(--text-muted)",
          maxWidth: 420,
          margin: "8px auto 0",
          lineHeight: 1.5,
        }}
      >
        Pick a category below and give it an amount. Next month I&apos;ll suggest
        the whole plan for you.
      </div>
    </Panel>
  );
}

function AssignMode() {
  const {
    month,
    toBeAssignedCents,
    draftIds,
    isFirstMonth,
    assign,
    confirmSuggestions,
    isLoading,
    isError,
    refetch,
    assignFailed,
    retryAssign,
    move,
    moveFailed,
    moveErrorCode,
    retryMove,
    dismissMoveError,
  } = useBudgetMonth();
  const [capsuleDismissed, setCapsuleDismissed] = React.useState(false);
  const [moveFrom, setMoveFrom] = React.useState<string | null>(null);
  const [scheduling, setScheduling] = React.useState<BudgetCategoryView | null>(null);
  const [breakdownOpen, setBreakdownOpen] = React.useState(false);

  if (isLoading) {
    return (
      <>
        <SkeletonPanel rows={1} rowHeight={72} />
        <SkeletonPanel rows={4} />
        <SkeletonPanel rows={3} />
      </>
    );
  }
  if (isError || !month) {
    return <ErrorPanel message="We couldn't load this month's budget." onRetry={() => refetch()} />;
  }

  const draftTotal = month.groups
    .flatMap((g) => g.categories)
    .filter((c) => c.suggestion_state === "draft")
    .reduce((a, c) => a + c.assigned_cents, 0);
  const totalCategories = month.groups.reduce((a, g) => a + g.categories.length, 0);
  const allDrafted = draftIds.length === totalCategories;

  const pendingNoun = draftIds.length === 1 ? "amount" : "amounts";
  const capsuleMessage = allDrafted
    ? `May's plan fits June — ${euroCents(draftTotal, 0)} across ${draftIds.length} categories`
    : `${draftIds.length} suggested ${pendingNoun} still pending`;

  return (
    <>
      <div className="tba-sticky">
        <TbaHero
          toBeAssignedCents={toBeAssignedCents}
          incomeCents={month.income_cents}
          carriedInCents={month.carried_in_cents}
          overspentDeductedCents={month.overspent_deducted_cents}
          onShowBreakdown={() => setBreakdownOpen(true)}
          action={
            draftIds.length > 0 && !capsuleDismissed ? (
              <Button variant="accent" size="sm" iconLeft="check" onClick={() => confirmSuggestions(draftIds)}>
                {allDrafted ? "Confirm all" : `Confirm remaining (${draftIds.length})`}
              </Button>
            ) : undefined
          }
        />
      </div>

      {/* Drafts surface through the coach capsule; dismissal ≠ confirmation. */}
      {draftIds.length > 0 && !capsuleDismissed && (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <CoachCapsule
              message={capsuleMessage}
              cta={allDrafted ? "Confirm all" : `Confirm remaining (${draftIds.length})`}
              onClick={() => confirmSuggestions(draftIds)}
            />
          </div>
          <IconButton
            icon="x"
            variant="ghost"
            size="sm"
            ariaLabel="Dismiss suggestions"
            onClick={() => setCapsuleDismissed(true)}
          />
        </div>
      )}

      {isFirstMonth && <FirstMonthEmptyState />}

      {assignFailed && (
        <div
          role="alert"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            background: "var(--expense-soft)",
            color: "var(--expense)",
            borderRadius: "var(--r-md)",
            padding: "10px 14px",
            font: "600 13.5px var(--font-sans)",
          }}
        >
          That amount didn&apos;t save — your budget is unchanged.
          <Button variant="secondary" size="sm" iconLeft="rotate-cw" onClick={retryAssign}>
            Retry
          </Button>
        </div>
      )}

      {moveFailed && (
        <div
          role="alert"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            background: "var(--expense-soft)",
            color: "var(--expense)",
            borderRadius: "var(--r-md)",
            padding: "10px 14px",
            font: "600 13.5px var(--font-sans)",
          }}
        >
          {moveErrorCode === "insufficient_available" || moveErrorCode === "insufficient_to_be_assigned"
            ? "That money isn't there anymore — your budget is unchanged."
            : "That move didn't save — your budget is unchanged."}
          <span style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" size="sm" onClick={dismissMoveError}>
              Dismiss
            </Button>
            <Button variant="secondary" size="sm" iconLeft="rotate-cw" onClick={retryMove}>
              Retry
            </Button>
          </span>
        </div>
      )}

      <CardMoveNote groups={month.groups} />

      <AssignGroups
        groups={month.groups}
        onAssign={assign}
        onCover={(c: BudgetCategoryView) => {
          if (!c.cover_suggestion) return;
          move({
            from_category_id: c.cover_suggestion.source_category_id,
            to_category_id: c.id,
            amount_cents: c.cover_suggestion.amount_cents,
          });
        }}
        onMove={(c: BudgetCategoryView) => setMoveFrom(c.id)}
        onSchedule={(c: BudgetCategoryView) => setScheduling(c)}
      />

      <IncomeBreakdown open={breakdownOpen} onOpenChange={setBreakdownOpen} view={month} />

      {scheduling && (
        <ScheduleEditor
          open
          onOpenChange={(open) => !open && setScheduling(null)}
          categoryId={scheduling.id}
          categoryName={scheduling.name}
          month={month.month}
          savedCents={scheduling.rollover_cents}
        />
      )}

      <MoveMoneySheet
        open={moveFrom !== null}
        onOpenChange={(open) => !open && setMoveFrom(null)}
        view={month}
        initialFrom={moveFrom ?? undefined}
        onMove={move}
      />
    </>
  );
}

export default function BudgetsPage() {
  const [mode, setMode] = React.useState("assign");

  return (
    <>
      <TopBar title="Budgets" sub="4 active this month" />
      <div className="app-content">
        <div style={{ maxWidth: 360 }}>
          <SegmentedControl
            options={[
              { value: "assign", label: "Assign" },
              { value: "report", label: "Report" },
            ]}
            value={mode}
            onChange={setMode}
          />
        </div>
        {mode === "assign" ? <AssignMode /> : <ReportMode />}
      </div>
    </>
  );
}

const CARD_MOVE_EXPLAINED_KEY = "olmenta-card-move-explained";

/* First card purchase: the money "moving" to the card's payment category is
   the least intuitive part of the YNAB card model — the coach explains it
   once (design D6, risks). */
function CardMoveNote({ groups }: Readonly<{ groups: BudgetGroupView[] }>) {
  // Lazy init is safe: the budget only renders once client data has loaded.
  const [explained, setExplained] = React.useState(() => {
    try {
      return globalThis.localStorage?.getItem(CARD_MOVE_EXPLAINED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const funded = groups
    .flatMap((g) => g.categories)
    .filter((c) => c.kind === "credit_payment")
    .map((c) => ({
      name: c.name,
      cents: c.available_cents - c.assigned_cents - c.rollover_cents + c.spent_cents,
    }))
    .find((c) => c.cents > 0);
  if (explained || !funded) return null;
  return (
    <CoachCapsule
      message={`You paid with a card, so I set aside ${euroCents(funded.cents)} in "${funded.name}" — the bill is already covered by your budget.`}
      cta="Got it"
      onClick={() => {
        try {
          globalThis.localStorage?.setItem(CARD_MOVE_EXPLAINED_KEY, "1");
        } catch {
          // Storage blocked: the note just shows again next time.
        }
        setExplained(true);
      }}
    />
  );
}
