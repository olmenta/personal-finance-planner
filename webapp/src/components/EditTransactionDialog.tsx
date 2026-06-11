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
import { PayeeField } from "@/components/PayeeField";
import {
  fetchCategories,
  fetchPayees,
  updateTransaction,
  type TransactionOut,
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
        <EditForm key={transaction.id} transaction={transaction} onClose={onClose} />
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
  const [amount, setAmount] = React.useState(
    money(Math.abs(transaction.amount_cents) / 100),
  );
  const [payee, setPayee] = React.useState(transaction.payee_name ?? "");
  const [note, setNote] = React.useState(transaction.description ?? "");
  const [category, setCategory] = React.useState(transaction.category_id ?? "");
  const [date, setDate] = React.useState(transaction.date);

  const queryClient = useQueryClient();
  const { data: groups } = useQuery({ queryKey: ["categories"], queryFn: fetchCategories });
  const { data: payees } = useQuery({ queryKey: ["payees"], queryFn: fetchPayees });

  const mutation = useMutation({
    mutationFn: () => {
      const amountCents = parseEuroToCents(amount);
      return updateTransaction(transaction.id, {
        amount_cents: amountCents ?? undefined,
        kind: direction === "Income" ? "income" : "expense",
        category_id: category || undefined,
        payee: payee.trim(), // "" clears
        note: note || null, // cleared text clears the description
        date,
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
      onClose();
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
                {(groups ?? []).map((g) => (
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
