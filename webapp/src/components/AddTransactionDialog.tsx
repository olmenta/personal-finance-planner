"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/shadcn/dialog";
import { Separator } from "@/components/shadcn/separator";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Switch } from "@/components/ui/Switch";
import { PayeeField } from "@/components/PayeeField";
import { CategoryCombobox } from "@/components/CategoryCombobox";
import { AccountSelect, useAccounts } from "@/components/AccountPicker";
import { useCoverPrompt } from "@/components/budget/CoverPrompt";
import {
  createTransaction,
  createTransfer,
  fetchCategories,
  fetchPayees,
} from "@/lib/api";
import { parseEuroToCents } from "@/lib/format";
import { invalidateMoneyQueries } from "@/lib/planQueries";

export interface AddTransactionDialogProps {
  children: React.ReactNode;
}

export function AddTransactionDialog({ children }: AddTransactionDialogProps) {
  const [open, setOpen] = React.useState(false);
  const [direction, setDirection] = React.useState("Expense");
  const [isRefund, setIsRefund] = React.useState(false);
  const [category, setCategory] = React.useState("");
  const [amount, setAmount] = React.useState("");
  const [payee, setPayee] = React.useState("");
  const [note, setNote] = React.useState("");
  const today = new Date().toISOString().split("T")[0];
  const [date, setDate] = React.useState(today);
  // "" = the main account (resolved at render, so it follows the first load).
  const [accountId, setAccountId] = React.useState("");
  const [toAccountId, setToAccountId] = React.useState("");

  const queryClient = useQueryClient();
  const { active: accounts, main } = useAccounts(open);
  const fromId = accountId || main?.id || "";
  const toId =
    toAccountId && toAccountId !== fromId
      ? toAccountId
      : (accounts.find((a) => a.id !== fromId)?.id ?? "");
  // One account: no picker, no transfers — entry stays as fast as before.
  const multiAccount = accounts.length > 1;
  const { data: groups } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
    enabled: open,
  });
  const { data: payees } = useQuery({
    queryKey: ["payees"],
    queryFn: fetchPayees,
    enabled: open,
  });

  // Active categories only: archived ones leave the pickers and must not be
  // prefilled either (spec: webapp-server-state).
  const categoryIds = React.useMemo(
    () =>
      new Set(
        (groups ?? []).flatMap((g) =>
          g.categories.filter((c) => !c.archived).map((c) => c.id),
        ),
      ),
    [groups],
  );

  function pickPayee(name: string, lastCategoryId: string | null) {
    setPayee(name);
    // Prefill, never override an explicit choice (design D4).
    if (!category && lastCategoryId && categoryIds.has(lastCategoryId)) {
      setCategory(lastCategoryId);
    }
  }

  function reset() {
    setOpen(false);
    setAmount("");
    setPayee("");
    setNote("");
    setCategory("");
    setIsRefund(false);
    setDate(today);
  }

  const transferMutation = useMutation({
    mutationFn: createTransfer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      invalidateMoneyQueries(queryClient);
      reset();
    },
  });

  const promptCover = useCoverPrompt();
  const mutation = useMutation({
    mutationFn: createTransaction,
    onSuccess: (_created, vars) => {
      // Overspent now? Offer the cover after the dialog closes (budget-rules D8).
      if (vars.category_id) void promptCover((vars.date ?? today).slice(0, 7), [vars.category_id]);
      // Spent totals changed — list, budget month, and dashboard summary are stale.
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      // Any month: the entry's date may not be the month on screen.
      invalidateMoneyQueries(queryClient);
      // A new payee may have been born from this write.
      queryClient.invalidateQueries({ queryKey: ["payees"] });
      reset();
    },
  });

  const isTransfer = direction === "Transfer" && multiAccount;
  const isIncome = direction === "Income";
  // A refund is an inflow that restores its category instead of counting as
  // income (spec: budget-api) — the category becomes required again.
  const needsCategory = !isIncome || isRefund;
  const amountCents = parseEuroToCents(amount);
  const pending = mutation.isPending || transferMutation.isPending;
  const canSubmit =
    (isTransfer ? !!fromId && !!toId && fromId !== toId : !needsCategory || !!category) &&
    amountCents !== null &&
    amountCents > 0 &&
    !pending;

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit || amountCents === null) return;
    if (isTransfer) {
      transferMutation.mutate({
        from_account_id: fromId,
        to_account_id: toId,
        amount_cents: amountCents,
        note: note || undefined,
        date,
      });
      return;
    }
    mutation.mutate({
      account_id: fromId || undefined,
      amount_cents: amountCents,
      category_id: needsCategory ? category : undefined,
      kind: isIncome ? "income" : "expense",
      payee: payee.trim() || undefined,
      note: note || undefined,
      date,
    });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>

      <DialogContent
        className="p-0 gap-0 overflow-hidden"
        style={{
          borderRadius: "var(--r-2xl)",
          maxWidth: 480,
          border: "1px solid var(--border-hairline)",
          boxShadow: "var(--shadow-xl)",
        }}
      >
        <DialogHeader
          style={{
            padding: "22px 24px 18px",
            borderBottom: "1px solid var(--border-hairline)",
          }}
        >
          <DialogTitle
            style={{
              font: "700 19px var(--font-sans)",
              letterSpacing: "-0.4px",
              color: "var(--text-strong)",
            }}
          >
            Add transaction
          </DialogTitle>
          <div style={{ marginTop: 12, width: multiAccount ? 360 : 280, maxWidth: "100%" }}>
            <SegmentedControl
              options={multiAccount ? ["Expense", "Income", "Transfer"] : ["Expense", "Income"]}
              defaultValue="Expense"
              onChange={setDirection}
            />
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
            <Input
              label="Amount"
              prefix="€"
              inputMode="decimal"
              placeholder="0,00"
              autoFocus
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              inputStyle={{
                font: "800 22px var(--font-sans)",
                letterSpacing: "-0.6px",
                fontVariantNumeric: "tabular-nums",
              }}
            />

            {isTransfer ? (
              <div style={{ display: "flex", gap: 12 }}>
                <AccountSelect
                  label="From"
                  value={fromId}
                  onChange={setAccountId}
                  accounts={accounts}
                />
                <AccountSelect
                  label="To"
                  value={toId}
                  onChange={setToAccountId}
                  accounts={accounts.filter((a) => a.id !== fromId)}
                />
              </div>
            ) : (
              <PayeeField
                label={direction === "Income" ? "Payer" : "Payee"}
                value={payee}
                payees={payees ?? []}
                onChange={setPayee}
                onPick={(p) => pickPayee(p.name, p.last_category_id)}
              />
            )}

            <Input
              label="Note"
              placeholder="Optional note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />

            {!isTransfer && isIncome && (
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 10,
                }}
              >
                <span
                  style={{
                    font: "600 13.5px var(--font-sans)",
                    color: "var(--text-body)",
                    letterSpacing: "-0.1px",
                  }}
                >
                  It&apos;s a refund
                  <span
                    style={{
                      display: "block",
                      font: "500 12px var(--font-sans)",
                      color: "var(--text-muted)",
                    }}
                  >
                    Returns the money to the category it was spent from
                  </span>
                </span>
                <Switch checked={isRefund} onChange={setIsRefund} />
              </label>
            )}
            {!isTransfer && needsCategory && (
            <label style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              <span
                style={{
                  font: "600 13.5px var(--font-sans)",
                  color: "var(--text-body)",
                  letterSpacing: "-0.1px",
                }}
              >
                Category
              </span>
              <CategoryCombobox value={category} onChange={setCategory} />
            </label>
            )}

            {!isTransfer && multiAccount && (
              <AccountSelect
                label="Account"
                value={fromId}
                onChange={setAccountId}
                accounts={accounts}
              />
            )}

            <Input
              label="Date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              inputStyle={{ font: "500 15px var(--font-sans)" }}
            />

            {(mutation.isError || transferMutation.isError) && (
              <div
                role="alert"
                style={{
                  font: "600 13px var(--font-sans)",
                  color: "var(--expense)",
                  background: "var(--expense-soft)",
                  borderRadius: "var(--r-md)",
                  padding: "9px 12px",
                }}
              >
                That didn&apos;t save — check the backend is running and try again.
              </div>
            )}
          </div>

          <Separator style={{ background: "var(--border-hairline)" }} />

          <div
            style={{
              padding: "16px 24px",
              display: "flex",
              justifyContent: "flex-end",
              gap: 10,
            }}
          >
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant={isIncome ? "accent" : "primary"}
              size="sm"
              type="submit"
              disabled={!canSubmit}
              iconLeft={isTransfer ? "arrow-left-right" : isIncome ? "trending-up" : "plus"}
            >
              {isTransfer ? "Add transfer" : isIncome ? "Add income" : "Add expense"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
