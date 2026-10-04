"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/shadcn/select";
import { fetchAccounts, type AccountOut, type TransactionOut } from "@/lib/api";

/** The user's accounts; `active` excludes archived ones (they leave pickers). */
export function useAccounts(enabled = true) {
  const query = useQuery({ queryKey: ["accounts"], queryFn: fetchAccounts, enabled });
  const all = query.data ?? [];
  const active = all.filter((a) => !a.archived);
  const main = active.find((a) => a.is_main) ?? active[0];
  return { ...query, all, active, main };
}

export function accountName(accounts: AccountOut[], id: string | null): string {
  return accounts.find((a) => a.id === id)?.name ?? "another account";
}

/* Transfer twins read as movement between accounts, never as income or
   spending (spec: transfer rendering stays neutral). */
export function transferTitle(t: TransactionOut, accounts: AccountOut[]): string {
  const other = accountName(accounts, t.transfer_account_id);
  return t.amount_cents < 0 ? `Transfer → ${other}` : `Transfer ← ${other}`;
}

export interface AccountSelectProps {
  label: string;
  value: string;
  onChange: (id: string) => void;
  accounts: AccountOut[];
  disabled?: boolean;
}

/* Labeled account dropdown, styled like the category select in the dialogs. */
export function AccountSelect({ label, value, onChange, accounts, disabled }: AccountSelectProps) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 7, minWidth: 0, flex: 1 }}>
      <span
        style={{
          font: "600 13.5px var(--font-sans)",
          color: "var(--text-body)",
          letterSpacing: "-0.1px",
        }}
      >
        {label}
      </span>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger
          className="h-12 rounded-[10px] border-[1.5px] text-sm font-medium"
          style={{
            borderColor: "var(--border-hairline)",
            color: value ? "var(--text-strong)" : "var(--text-subtle)",
            background: "var(--surface)",
            fontFamily: "var(--font-sans)",
          }}
        >
          <SelectValue placeholder="Select account" />
        </SelectTrigger>
        <SelectContent
          style={{
            borderRadius: "var(--r-md)",
            border: "1px solid var(--border-hairline)",
            boxShadow: "var(--shadow-lg)",
          }}
        >
          {accounts.map((a) => (
            <SelectItem key={a.id} value={a.id}>
              {a.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}
