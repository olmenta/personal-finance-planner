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
import {
  createTransaction,
  currentMonth,
  fetchCategories,
} from "@/lib/api";
import { parseEuroToCents } from "@/lib/format";

export interface AddTransactionDialogProps {
  children: React.ReactNode;
}

export function AddTransactionDialog({ children }: AddTransactionDialogProps) {
  const [open, setOpen] = React.useState(false);
  const [direction, setDirection] = React.useState("Expense");
  const [category, setCategory] = React.useState("");
  const [amount, setAmount] = React.useState("");
  const [note, setNote] = React.useState("");
  const today = new Date().toISOString().split("T")[0];
  const [date, setDate] = React.useState(today);

  const queryClient = useQueryClient();
  const { data: groups } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: createTransaction,
    onSuccess: () => {
      // Spent totals changed — list, budget month, and dashboard summary are stale.
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["budget", currentMonth()] });
      queryClient.invalidateQueries({ queryKey: ["summary", currentMonth()] });
      setOpen(false);
      setAmount("");
      setNote("");
      setCategory("");
      setDate(today);
    },
  });

  const amountCents = parseEuroToCents(amount);
  const canSubmit = !!category && amountCents !== null && amountCents > 0 && !mutation.isPending;

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit || amountCents === null) return;
    mutation.mutate({
      amount_cents: amountCents,
      category_id: category,
      kind: direction === "Income" ? "income" : "expense",
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
          <div style={{ marginTop: 12, width: 280 }}>
            <SegmentedControl
              options={["Expense", "Income"]}
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

            <Input
              label="Merchant or description"
              placeholder="e.g. Mercadona"
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
                      {g.categories.map((c) => (
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
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant={direction === "Income" ? "accent" : "primary"}
              size="sm"
              type="submit"
              disabled={!canSubmit}
              iconLeft={direction === "Income" ? "trending-up" : "plus"}
            >
              {direction === "Income" ? "Add income" : "Add expense"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
