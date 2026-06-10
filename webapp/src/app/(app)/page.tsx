import { AddTransactionDialog } from "@/components/AddTransactionDialog";
import { BalanceCard } from "@/components/ui/BalanceCard";
import { Badge } from "@/components/ui/Badge";
import { BudgetBar } from "@/components/ui/BudgetBar";
import { Button } from "@/components/ui/Button";
import { CoachCapsule } from "@/components/ui/CoachCapsule";
import { Icon } from "@/components/ui/Icon";
import { Panel } from "@/components/ui/Panel";
import { StatCard } from "@/components/ui/StatCard";
import { TransactionRow } from "@/components/ui/TransactionRow";
import { TopBar } from "@/components/shell/TopBar";
import { balance, budgets, transactions, weeks } from "@/lib/mock-data";

function SpendChart() {
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
            Saved
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
        {weeks.map((w) => (
          <div
            key={w.l}
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
                  height: `${w.a}%`,
                  background: "var(--grad-balance)",
                  borderRadius: "6px 6px 3px 3px",
                }}
              />
              <div
                style={{
                  width: 14,
                  height: `${w.b}%`,
                  background: "var(--mint-300)",
                  borderRadius: "6px 6px 3px 3px",
                }}
              />
            </div>
            <span style={{ font: "600 12px var(--font-sans)", color: "var(--text-subtle)" }}>
              {w.l}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export default function OverviewPage() {
  return (
    <>
      <TopBar title="Overview" sub="Welcome back, Maya" />
      <div className="app-content">
        <div className="grid-dash-top">
          <BalanceCard
            label="Current balance"
            amount={balance.amount}
            cents={balance.cents}
            align="left"
            delta={
              <>
                <Icon name="trending-up" size={15} /> {balance.delta}
              </>
            }
            style={{ borderRadius: "var(--r-xl)" }}
          />
          <StatCard icon="trending-up" tone="income" label="Income" value={balance.income} />
          <StatCard icon="trending-down" tone="expense" label="Expenses" value={balance.expenses} />
        </div>

        {/* The web reference keeps coach insights in the rail; the capsule
            appears only when the rail is collapsed (<1440px). */}
        <div className="coach-capsule-fallback">
          <CoachCapsule message="You're spending 18% more on dining this month" cta="See why" />
        </div>

        <div className="grid-dash-mid">
          <SpendChart />
          <Panel title="Budgets" action={<Badge tone="brand">4 active</Badge>}>
            <div style={{ display: "flex", flexDirection: "column", gap: 17 }}>
              {budgets.map((b) => (
                <BudgetBar key={b.label} {...b} />
              ))}
            </div>
          </Panel>
        </div>

        <Panel
          title="Recent transactions"
          action={
            <div style={{ display: "flex", gap: 8 }}>
              <AddTransactionDialog>
                <Button variant="primary" size="sm" iconLeft="plus">
                  Add transaction
                </Button>
              </AddTransactionDialog>
              <Button variant="ghost" size="sm" iconRight="chevron-right">
                View all
              </Button>
            </div>
          }
        >
          <div style={{ display: "flex", flexDirection: "column" }}>
            {transactions.slice(0, 4).map((t, i) => (
              <div
                key={t.title}
                style={{
                  borderBottom: i < 3 ? "1px solid var(--border-hairline)" : "none",
                }}
              >
                <TransactionRow
                  icon={t.icon}
                  tone={t.tone}
                  title={t.title}
                  subtitle={t.subtitle}
                  amount={t.amount}
                  direction={t.direction}
                  card={false}
                />
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}
