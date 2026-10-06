"use client";

import React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/shadcn/select";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import type { SchedulePattern } from "@/lib/api";
import {
  MONTH_NAMES,
  MONTH_SHORT,
  PATTERNS,
  monthFromIndex,
  monthIndex,
  monthLabel,
} from "@/lib/schedules";

/* The "when money moves" part of a schedule form, shared by the payment
   editor and the income editor (income-schedules design D8). */

export interface RuleDraft {
  pattern: SchedulePattern;
  months: number[];
  month: number;
  everyN: number;
  startMonth: string;
  count: string;
  onceMonth: string;
  day: string;
  estimated: boolean;
}

interface RuleSource {
  pattern: SchedulePattern;
  months: number[] | null;
  month: number | null;
  every_n: number | null;
  start_month: string | null;
  count: number | null;
  once_month: string | null;
  day: number | null;
  estimated: boolean;
}

export function ruleDraftFrom(
  s: RuleSource | null,
  month: string,
  defaultMonths: number[] = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6],
): RuleDraft {
  return {
    pattern: s?.pattern ?? "monthly",
    months: s?.months ?? defaultMonths,
    month: s?.month ?? Number(month.slice(5, 7)),
    everyN: s?.every_n ?? 3,
    startMonth: s?.start_month ?? month,
    count: s?.count ? String(s.count) : "",
    onceMonth: s?.once_month ?? month,
    day: s?.day ? String(s.day) : "",
    estimated: s?.estimated ?? false,
  };
}

export type RuleBody =
  | { pattern: "monthly"; count?: number; start_month?: string }
  | { pattern: "some_months"; months: number[] }
  | { pattern: "annual"; month: number }
  | { pattern: "every_n"; every_n: number; start_month: string }
  | { pattern: "once"; once_month: string }
  | { pattern: "no_date" };

/** The pattern fields of the API body, or null when the draft is incomplete. */
export function ruleBody(d: RuleDraft): RuleBody | null {
  switch (d.pattern) {
    case "monthly":
      return d.count
        ? { pattern: "monthly", count: Number(d.count), start_month: d.startMonth }
        : { pattern: "monthly" };
    case "some_months":
      return d.months.length ? { pattern: "some_months", months: d.months } : null;
    case "annual":
      return { pattern: "annual", month: d.month };
    case "every_n":
      return { pattern: "every_n", every_n: d.everyN, start_month: d.startMonth };
    case "once":
      return { pattern: "once", once_month: d.onceMonth };
    default:
      return { pattern: "no_date" };
  }
}

export const ruleDay = (d: RuleDraft): number | null =>
  d.day ? Math.min(31, Math.max(1, Number(d.day))) : null;

export const triggerStyle: React.CSSProperties = {
  borderColor: "var(--border-hairline)",
  color: "var(--text-strong)",
  background: "var(--surface)",
  fontFamily: "var(--font-sans)",
};

export function Field({ label, children }: Readonly<{ label: string; children: React.ReactNode }>) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-body)" }}>{label}</span>
      {children}
    </label>
  );
}

function MonthSelect({
  value,
  onChange,
  choices,
}: Readonly<{ value: string; onChange: (v: string) => void; choices: string[] }>) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-11 rounded-[10px] border-[1.5px] text-sm font-medium" style={triggerStyle}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {choices.map((m) => (
          <SelectItem key={m} value={m}>{monthLabel(m)}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export interface ScheduleRuleFieldsProps {
  draft: RuleDraft;
  onChange: <K extends keyof RuleDraft>(key: K, value: RuleDraft[K]) => void;
  /** Month the pickers start from (the month on screen). */
  month: string;
  /** Rendered between the pattern picker and the pattern's own fields. */
  amountField: React.ReactNode;
  /** Income has no "no date" pattern. */
  allowNoDate?: boolean;
  /** Copy that differs between payments and income. */
  labels?: {
    pattern?: string;
    months?: string;
    next?: string;
    count?: string;
    estimated?: string;
    estimatedHint?: string;
  };
}

export function ScheduleRuleFields({
  draft,
  onChange: set,
  month,
  amountField,
  allowNoDate = true,
  labels = {},
}: Readonly<ScheduleRuleFieldsProps>) {
  const monthChoices = Array.from({ length: 18 }, (_, k) => monthFromIndex(monthIndex(month) + k));
  const patterns = allowNoDate ? PATTERNS : PATTERNS.filter((p) => p.value !== "no_date");

  return (
    <>
      <Field label={labels.pattern ?? "How it's paid"}>
        <Select value={draft.pattern} onValueChange={(v) => set("pattern", v as SchedulePattern)}>
          <SelectTrigger className="h-11 rounded-[10px] border-[1.5px] text-sm font-medium" style={triggerStyle}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {patterns.map((p) => (
              <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      {amountField}

      {draft.pattern === "some_months" && (
        <Field label={labels.months ?? "Months it's paid"}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {MONTH_SHORT.map((m, i) => {
              const on = draft.months.includes(i + 1);
              return (
                <button
                  type="button"
                  key={m}
                  aria-pressed={on}
                  onClick={() =>
                    set("months", on ? draft.months.filter((x) => x !== i + 1) : [...draft.months, i + 1])
                  }
                  style={{
                    border: "none",
                    minWidth: 46,
                    padding: "6px 10px",
                    borderRadius: "var(--r-full)",
                    font: "600 12.5px var(--font-sans)",
                    cursor: "pointer",
                    background: on ? "var(--brand)" : "var(--surface)",
                    color: on ? "#fff" : "var(--text-muted)",
                  }}
                >
                  {m}
                </button>
              );
            })}
          </div>
        </Field>
      )}
      {draft.pattern === "annual" && (
        <Field label="Month">
          <Select value={String(draft.month)} onValueChange={(v) => set("month", Number(v))}>
            <SelectTrigger className="h-11 rounded-[10px] border-[1.5px] text-sm font-medium" style={triggerStyle}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MONTH_NAMES.map((m, i) => (
                <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      )}
      {draft.pattern === "every_n" && (
        <div className="grid-2">
          <Field label="Every">
            <Select value={String(draft.everyN)} onValueChange={(v) => set("everyN", Number(v))}>
              <SelectTrigger className="h-11 rounded-[10px] border-[1.5px] text-sm font-medium" style={triggerStyle}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[2, 3, 4, 6].map((n) => (
                  <SelectItem key={n} value={String(n)}>{n} months</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label={labels.next ?? "Next payment"}>
            <MonthSelect value={draft.startMonth} onChange={(v) => set("startMonth", v)} choices={monthChoices} />
          </Field>
        </div>
      )}
      {draft.pattern === "once" && (
        <Field label="When">
          <MonthSelect value={draft.onceMonth} onChange={(v) => set("onceMonth", v)} choices={monthChoices} />
        </Field>
      )}
      {draft.pattern === "monthly" && (
        <Input
          label={labels.count ?? "Number of payments (empty = no end)"}
          inputMode="numeric"
          placeholder="—"
          value={draft.count}
          onChange={(e) => set("count", e.target.value.replace(/\D/g, ""))}
        />
      )}
      {draft.pattern !== "no_date" && (
        <Input
          label="Day of the month (optional)"
          inputMode="numeric"
          placeholder="—"
          value={draft.day}
          onChange={(e) => set("day", e.target.value.replace(/\D/g, "").slice(0, 2))}
        />
      )}
      {draft.pattern !== "no_date" && (
        <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
          <span style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-body)" }}>
            {labels.estimated ?? "The amount varies"}
            <span style={{ display: "block", font: "500 12px var(--font-sans)", color: "var(--text-muted)" }}>
              {labels.estimatedHint ?? "Bills like water or electricity: any bill that arrives counts as paid"}
            </span>
          </span>
          <Switch checked={draft.estimated} onChange={(v) => set("estimated", v)} />
        </label>
      )}
    </>
  );
}
