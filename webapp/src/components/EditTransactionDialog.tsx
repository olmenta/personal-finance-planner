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
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/shadcn/select";
import { Separator } from "@/components/shadcn/separator";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Switch } from "@/components/ui/Switch";
import { PayeeField } from "@/components/PayeeField";
import { AccountSelect, useAccounts } from "@/components/AccountPicker";
import { invalidateMoneyQueries } from "@/lib/planQueries";
import { useCoverPrompt } from "@/components/budget/CoverPrompt";
import {
  fetchCategories,
  fetchPayees,
  fetchTransfer,
  unlinkTransfer,
  updateTransaction,
  updateTransfer,
  type TransactionOut,
  type TransferOut,
} from "@/lib/api";
import { money, parseEuroToCents } from "@/lib/format";

export interface EditTransactionDialogProps {
  transaction: TransactionOut | null; // null = closed
  onClose: () => void;
}

export function EditTransactionDialog({
  transaction,
  onClose,
}: EditTransactionDialogProps) {
  return (
    <Dialog open={transaction !== null} onOpenChange={(o) => !o && onClose()}>
      {transaction && (
        // Keyed by row so state re-initializes per transaction, no effects.
        transaction.transfer_pair_id ? (
          <TransferEditLoader
            key={transaction.id}
            pairId={transaction.transfer_pair_id}
            onClose={onClose}
          />
        ) : (
          <EditForm key={transaction.id} transaction={transaction} onClose={onClose} />
        )
      )}
    </Dialog>
  );
}

function EditForm({
  transaction,
  onClose,
}: Readonly<{ transaction: TransactionOut; onClose: () => void }>) {
  const wasIncome = transaction.amount_cents > 0;
  const [direction, setDirection] = React.useState(wasIncome ? "Income" : "Expense");
  // An income row that already carries a category is a refund.
  const [isRefund, setIsRefund] = React.useState(
    wasIncome && transaction.category_id !== null,
  );
  const [amount, setAmount] = React.useState(
    money(Math.abs(transaction.amount_cents) / 100),
  );
  const [payee, setPayee] = React.useState(transaction.payee_name ?? "");
  const [note, setNote] = React.useState(transaction.description ?? "");
  const [category, setCategory] = React.useState(transaction.category_id ?? "");
  const [date, setDate] = React.useState(transaction.date);
  const [accountId, setAccountId] = React.useState(transaction.account_id);

  const queryClient = useQueryClient();
  const { active: accounts } = useAccounts();
  const { data: groups } = useQuery({ queryKey: ["categories"], queryFn: fetchCategories });
  const { data: payees } = useQuery({ queryKey: ["payees"], queryFn: fetchPayees });

  const isIncome = direction === "Income";
  // Refund = inflow that restores its category (spec: budget-api).
  const needsCategory = !isIncome || isRefund;

  const promptCover = useCoverPrompt();
  const mutation = useMutation({
    mutationFn: () => {
      const amountCents = parseEuroToCents(amount);
      return updateTransaction(transaction.id, {
        amount_cents: amountCents ?? undefined,
        kind: isIncome ? "income" : "expense",
        // Refund off on an income row → null clears the stored category so
        // the inflow counts as income again; absent leaves it untouched.
        category_id: needsCategory ? category || undefined : null,
        payee: payee.trim(), // "" clears
        note: note || null, // cleared text clears the description
        date,
        account_id: accountId !== transaction.account_id ? accountId : undefined,
      });
    },
    onSuccess: (updated) => {
      // Totals changed in the row's old month and (if the date moved) the
      // new one — invalidate both (design D5).
      const months = new Set([transaction.date.slice(0, 7), updated.date.slice(0, 7)]);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["payees"] });
      for (const m of months) {
        queryClient.invalidateQueries({ queryKey: ["budget", m] });
        queryClient.invalidateQueries({ queryKey: ["summary", m] });
      }
      invalidateMoneyQueries(queryClient);
      onClose();
      // Overspent now? Offer the cover after the dialog closes (budget-rules D8).
      if (updated.category_id) void promptCover(updated.date.slice(0, 7), [updated.category_id]);
    },
  });

  const amountCents = parseEuroToCents(amount);
  const canSubmit = amountCents !== null && amountCents > 0 && !mutation.isPending;

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit) return;
    mutation.mutate();
  }

  return (
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
          Edit transaction
        </DialogTitle>
        <div style={{ marginTop: 12, width: 280 }}>
          <SegmentedControl
            options={["Expense", "Income"]}
            defaultValue={wasIncome ? "Income" : "Expense"}
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

          <PayeeField
            label={direction === "Income" ? "Payer" : "Payee"}
            value={payee}
            payees={payees ?? []}
            onChange={setPayee}
            onPick={(p) => setPayee(p.name)}
          />

          <Input
            label="Note"
            placeholder="Optional note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />

          {isIncome && (
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
          {needsCategory && (
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
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger
                className="h-12 rounded-[10px] border-[1.5px] text-sm font-medium"
                style={{
                  borderColor: "var(--border-hairline)",
                  color: category ? "var(--text-strong)" : "var(--text-subtle)",
                  background: "var(--surface)",
                  fontFamily: "var(--font-sans)",
                }}
              >
                <SelectValue
                  placeholder={groups ? "Select category" : "Loading categories…"}
                />
              </SelectTrigger>
              <SelectContent
                style={{
                  borderRadius: "var(--r-md)",
                  border: "1px solid var(--border-hairline)",
                  boxShadow: "var(--shadow-lg)",
                }}
              >
                {(groups ?? []).filter((g) => !g.system).map((g) => (
                  <SelectGroup key={g.id}>
                    <SelectLabel>{g.name}</SelectLabel>
                    {g.categories.filter((c) => !c.archived).map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
          </label>
          )}

          {accounts.length > 1 && (
            <AccountSelect
              label="Account"
              value={accountId}
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

          {mutation.isError && (
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
          <Button variant="ghost" size="sm" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" type="submit" disabled={!canSubmit}>
            Save changes
          </Button>
        </div>
      </form>
    </DialogContent>
  );
}

const contentStyle: React.CSSProperties = {
  borderRadius: "var(--r-2xl)",
  maxWidth: 480,
  border: "1px solid var(--border-hairline)",
  boxShadow: "var(--shadow-xl)",
};

const titleStyle: React.CSSProperties = {
  font: "700 19px var(--font-sans)",
  letterSpacing: "-0.4px",
  color: "var(--text-strong)",
};

/* Either twin opens the same pair: the transfer contract edits both. */
function TransferEditLoader({
  pairId,
  onClose,
}: Readonly<{ pairId: string; onClose: () => void }>) {
  const { data: transfer, isError } = useQuery({
    queryKey: ["transfer", pairId],
    queryFn: () => fetchTransfer(pairId),
  });
  if (!transfer) {
    return (
      <DialogContent className="p-0 gap-0 overflow-hidden" style={contentStyle}>
        <DialogHeader style={{ padding: "22px 24px" }}>
          <DialogTitle style={titleStyle}>Edit transfer</DialogTitle>
          <p style={{ font: "500 14px var(--font-sans)", color: "var(--text-muted)", margin: 0 }}>
            {isError ? "That transfer couldn't load — try again." : "Loading…"}
          </p>
        </DialogHeader>
      </DialogContent>
    );
  }
  return <TransferEditForm transfer={transfer} onClose={onClose} />;
}

function TransferEditForm({
  transfer,
  onClose,
}: Readonly<{ transfer: TransferOut; onClose: () => void }>) {
  const [amount, setAmount] = React.useState(money(transfer.amount_cents / 100));
  const [note, setNote] = React.useState(transfer.note ?? "");
  const [date, setDate] = React.useState(transfer.date);
  const { all: accounts } = useAccounts();
  const queryClient = useQueryClient();

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["transactions"] });
    queryClient.invalidateQueries({ queryKey: ["transfer", transfer.pair_id] });
    invalidateMoneyQueries(queryClient);
    onClose();
  }

  const save = useMutation({
    mutationFn: () =>
      updateTransfer(transfer.pair_id, {
        amount_cents: parseEuroToCents(amount) ?? undefined,
        note: note || null,
        date,
      }),
    onSuccess: refresh,
  });
  // A mistaken pair splits back into two ordinary rows that count again.
  const unlink = useMutation({
    mutationFn: () => unlinkTransfer(transfer.pair_id),
    onSuccess: refresh,
  });

  const amountCents = parseEuroToCents(amount);
  const pending = save.isPending || unlink.isPending;
  const canSubmit = amountCents !== null && amountCents > 0 && !pending;

  return (
    <DialogContent className="p-0 gap-0 overflow-hidden" style={contentStyle}>
      <DialogHeader
        style={{ padding: "22px 24px 18px", borderBottom: "1px solid var(--border-hairline)" }}
      >
        <DialogTitle style={titleStyle}>Edit transfer</DialogTitle>
      </DialogHeader>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) save.mutate();
        }}
      >
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

          <div style={{ display: "flex", gap: 12 }}>
            <AccountSelect
              label="From"
              value={transfer.from_account_id}
              onChange={() => undefined}
              accounts={accounts}
              disabled
            />
            <AccountSelect
              label="To"
              value={transfer.to_account_id}
              onChange={() => undefined}
              accounts={accounts}
              disabled
            />
          </div>

          <Input
            label="Note"
            placeholder="Optional note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />

          <Input
            label="Date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            inputStyle={{ font: "500 15px var(--font-sans)" }}
          />

          {(save.isError || unlink.isError) && (
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

        <div style={{ padding: "16px 24px", display: "flex", alignItems: "center", gap: 10 }}>
          <Button
            variant="ghost"
            size="sm"
            type="button"
            disabled={pending}
            onClick={() => unlink.mutate()}
          >
            Unlink transfer
          </Button>
          <div style={{ flex: 1 }} />
          <Button variant="ghost" size="sm" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" type="submit" disabled={!canSubmit}>
            Save changes
          </Button>
        </div>
      </form>
    </DialogContent>
  );
}
