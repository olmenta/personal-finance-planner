"use client";

import React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/shadcn/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/shadcn/select";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { BudgetMonthView, MoveRequest } from "@/lib/api";
import { euroCents, money, parseEuroToCents } from "@/lib/format";

/* Sentinel for "To Be Assigned" as a source in the picker (API: null). */
const UNASSIGNED = "__unassigned__";

export interface MoveMoneySheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  view: BudgetMonthView;
  /** Preselected source (row "Move money") — null = To Be Assigned. */
  initialFrom?: string | null;
  /** Preselected target ("Choose another" on a cover prompt). */
  initialTo?: string;
  onMove: (move: MoveRequest) => void;
}

const selectTriggerStyle: React.CSSProperties = {
  borderColor: "var(--border-hairline)",
  color: "var(--text-strong)",
  background: "var(--surface)",
  fontFamily: "var(--font-sans)",
};

function Field({ label, children }: Readonly<{ label: string; children: React.ReactNode }>) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-body)" }}>{label}</span>
      {children}
    </label>
  );
}

/* Move money between categories within the month (budget-rules): the way
   to cover overspending or re-plan. The amount is capped by the source's
   available in the form itself, not only by the server. */
export function MoveMoneySheet({
  open,
  onOpenChange,
  view,
  initialFrom,
  initialTo,
  onMove,
}: Readonly<MoveMoneySheetProps>) {
  const categories = view.groups.flatMap((g) => g.categories);
  const toBeAssigned = Math.max(0, view.to_be_assigned_cents);

  const [from, setFrom] = React.useState("");
  const [to, setTo] = React.useState("");
  const [amount, setAmount] = React.useState("");

  // Re-seed the form each time the sheet opens for a different row.
  const seedKey = open ? `${initialFrom ?? UNASSIGNED}|${initialTo ?? ""}` : null;
  const [seeded, setSeeded] = React.useState<string | null>(null);
  if (seedKey !== seeded) {
    setSeeded(seedKey);
    if (seedKey !== null) {
      const target = categories.find((c) => c.id === initialTo);
      setFrom(initialFrom === undefined ? "" : (initialFrom ?? UNASSIGNED));
      setTo(initialTo ?? "");
      setAmount(target && target.overspent_cents > 0 ? money(target.overspent_cents / 100) : "");
    }
  }

  const sources = categories.filter((c) => c.available_cents > 0 && c.id !== to);
  const targets = categories.filter((c) => c.id !== from);
  const sourceAvailable =
    from === UNASSIGNED
      ? toBeAssigned
      : (categories.find((c) => c.id === from)?.available_cents ?? 0);

  const cents = parseEuroToCents(amount);
  const tooMuch = cents !== null && cents > sourceAvailable;
  const canSubmit = !!from && !!to && from !== to && cents !== null && cents > 0 && !tooMuch;

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit || cents === null) return;
    onMove({
      from_category_id: from === UNASSIGNED ? null : from,
      to_category_id: to,
      amount_cents: cents,
    });
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="p-0 gap-0 overflow-hidden"
        style={{
          borderRadius: "var(--r-2xl)",
          maxWidth: 440,
          border: "1px solid var(--border-hairline)",
          boxShadow: "var(--shadow-xl)",
        }}
      >
        <DialogHeader style={{ padding: "22px 24px 16px", borderBottom: "1px solid var(--border-hairline)" }}>
          <DialogTitle
            style={{ font: "700 19px var(--font-sans)", letterSpacing: "-0.4px", color: "var(--text-strong)" }}
          >
            Move money
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
            <Field label="From">
              <Select value={from} onValueChange={setFrom}>
                <SelectTrigger className="h-12 rounded-[10px] border-[1.5px] text-sm font-medium" style={selectTriggerStyle}>
                  <SelectValue placeholder="Where the money comes from" />
                </SelectTrigger>
                <SelectContent>
                  {toBeAssigned > 0 && (
                    <SelectItem value={UNASSIGNED}>Unassigned · {euroCents(toBeAssigned)}</SelectItem>
                  )}
                  {sources.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name} · {euroCents(c.available_cents)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>

            <Field label="To">
              <Select value={to} onValueChange={setTo}>
                <SelectTrigger className="h-12 rounded-[10px] border-[1.5px] text-sm font-medium" style={selectTriggerStyle}>
                  <SelectValue placeholder="Where it goes" />
                </SelectTrigger>
                <SelectContent>
                  {targets.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                      {c.overspent_cents > 0 ? ` · over ${euroCents(c.overspent_cents)}` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>

            <Input
              label="Amount"
              prefix="€"
              inputMode="decimal"
              placeholder="0,00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              inputStyle={{ font: "800 20px var(--font-sans)", letterSpacing: "-0.5px", fontVariantNumeric: "tabular-nums" }}
            />
            {from && (
              <div
                style={{
                  font: "500 12.5px var(--font-sans)",
                  color: tooMuch ? "var(--expense)" : "var(--text-muted)",
                  marginTop: -8,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {tooMuch
                  ? `Only ${euroCents(sourceAvailable)} available there`
                  : `${euroCents(sourceAvailable)} available`}
              </div>
            )}
          </div>
          <div
            style={{
              padding: "14px 24px 20px",
              display: "flex",
              justifyContent: "flex-end",
              gap: 10,
              borderTop: "1px solid var(--border-hairline)",
            }}
          >
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit}>
              Move money
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
