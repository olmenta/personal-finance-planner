"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { AddTransactionDialog } from "@/components/AddTransactionDialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconChip } from "@/components/ui/IconChip";
import { ErrorPanel, SkeletonPanel } from "@/components/ui/QueryStates";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { TopBar } from "@/components/shell/TopBar";
import {
  currentMonth,
  fetchCategories,
  fetchTransactions,
  toneForCategory,
  type CategoryOut,
  type TransactionOut,
} from "@/lib/api";
import { euroCents } from "@/lib/format";

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function TxTable({
  rows,
  categories,
}: Readonly<{ rows: TransactionOut[]; categories: Map<string, CategoryOut> }>) {
  return (
    <div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1.2fr 1fr 0.9fr",
          gap: 16,
          padding: "0 6px 12px",
          borderBottom: "1px solid var(--border-hairline)",
        }}
      >
        {["Transaction", "Category", "Date", "Amount"].map((h, i) => (
          <span
            key={h}
            className="ol-eyebrow"
            style={{ color: "var(--text-subtle)", textAlign: i === 3 ? "right" : "left" }}
          >
            {h}
          </span>
        ))}
      </div>
      {rows.map((r, i) => {
        const category = r.category_id ? categories.get(r.category_id) : undefined;
        const isIncome = r.amount_cents > 0;
        return (
          <div
            key={r.id}
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1.2fr 1fr 0.9fr",
              gap: 16,
              alignItems: "center",
              padding: "13px 6px",
              borderBottom: i < rows.length - 1 ? "1px solid var(--border-hairline)" : "none",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <IconChip
                icon={isIncome ? "dollar-sign" : (category?.icon ?? "circle")}
                tone={isIncome ? "income" : toneForCategory(category?.icon ?? "circle")}
                size={40}
              />
              <div>
                <div
                  style={{
                    font: "600 14.5px var(--font-sans)",
                    color: "var(--text-strong)",
                    letterSpacing: "-0.1px",
                  }}
                >
                  {r.description ?? category?.name ?? "Transaction"}
                </div>
                <div style={{ font: "500 12px var(--font-mono)", color: "var(--text-subtle)" }}>
                  {r.source === "manual" ? "Manual entry" : r.source}
                </div>
              </div>
            </div>
            <div>
              <Badge tone={isIncome ? "income" : "brand"} dot>
                {category?.name ?? "Uncategorized"}
              </Badge>
            </div>
            <div style={{ font: "500 13.5px var(--font-sans)", color: "var(--text-muted)" }}>
              {formatDate(r.date)}
            </div>
            <div
              style={{
                textAlign: "right",
                font: "700 14.5px var(--font-sans)",
                fontVariantNumeric: "tabular-nums",
                color: isIncome ? "var(--income)" : "var(--text-strong)",
              }}
            >
              {isIncome ? "+" : "−"}
              {euroCents(Math.abs(r.amount_cents))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{ textAlign: "center", padding: "40px 0" }}>
      <div
        style={{
          font: "700 18px var(--font-sans)",
          letterSpacing: "-0.3px",
          color: "var(--text-strong)",
        }}
      >
        Nothing here yet — add your first transaction
      </div>
      <div
        style={{
          font: "500 14px var(--font-sans)",
          color: "var(--text-muted)",
          margin: "8px 0 18px",
        }}
      >
        Every euro you track makes your budget smarter.
      </div>
      <AddTransactionDialog>
        <Button variant="primary" iconLeft="plus">
          Add transaction
        </Button>
      </AddTransactionDialog>
    </div>
  );
}

export default function TransactionsPage() {
  const month = currentMonth();
  const [filter, setFilter] = React.useState("All");

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

  const rows = (txQuery.data ?? []).filter((t) => {
    if (filter === "Expenses") return t.amount_cents < 0;
    if (filter === "Income") return t.amount_cents > 0;
    return true;
  });

  const count = txQuery.data?.length;

  let body: React.ReactNode;
  if (txQuery.isPending || catQuery.isPending) {
    body = <SkeletonPanel rows={6} rowHeight={48} />;
  } else if (txQuery.isError || catQuery.isError) {
    body = (
      <ErrorPanel
        message="We couldn't load your transactions."
        onRetry={() => {
          txQuery.refetch();
          catQuery.refetch();
        }}
      />
    );
  } else {
    body = (
      <section
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border-hairline)",
          borderRadius: "var(--r-xl)",
          padding: 22,
          boxShadow: "var(--shadow-sm)",
        }}
      >
        {rows.length === 0 ? <EmptyState /> : <TxTable rows={rows} categories={categories} />}
      </section>
    );
  }

  return (
    <>
      <TopBar
        title="Transactions"
        sub={count === undefined ? "This month" : `${count} this month`}
      />
      <div className="app-content">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <div style={{ width: 320, maxWidth: "100%" }}>
            <SegmentedControl
              options={["All", "Expenses", "Income"]}
              defaultValue="All"
              onChange={setFilter}
            />
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <Button variant="ghost" size="sm" iconLeft="filter">
              Filter
            </Button>
            <AddTransactionDialog>
              <Button variant="primary" size="sm" iconLeft="plus">
                Add transaction
              </Button>
            </AddTransactionDialog>
          </div>
        </div>
        {body}
      </div>
    </>
  );
}
