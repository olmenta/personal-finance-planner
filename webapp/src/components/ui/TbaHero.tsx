import React from "react";
import { euroCents } from "@/lib/format";
import { Icon } from "./Icon";

export interface TbaHeroProps {
  toBeAssignedCents: number;
  incomeCents: number;
  /** Previous month's To Be Assigned (carries over). */
  carriedInCents?: number;
  /** Previous month's uncovered overspending, deducted here. */
  overspentDeductedCents?: number;
  /** Opens the breakdown of where the money to assign comes from. */
  onShowBreakdown?: () => void;
  action?: React.ReactNode;
}

/* "To be assigned" hero — the number the zero-based method optimizes.
   Three money-semantic states (design.md D2): violet >0, mint =0, red <0. */
export function TbaHero({
  toBeAssignedCents,
  incomeCents,
  carriedInCents = 0,
  overspentDeductedCents = 0,
  onShowBreakdown,
  action,
}: TbaHeroProps) {
  // To Be Assigned carries over (budget-rules): say where the number comes from.
  // Income is money entering the budget: semantic green (design system).
  const income = (
    <>
      of{" "}
      <b style={{ color: "var(--income)", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
        {euroCents(incomeCents)}
      </b>{" "}
      income this month
    </>
  );
  const breakdown: string[] = [];
  if (carriedInCents > 0) breakdown.push(`includes ${euroCents(carriedInCents)} from last month`);
  if (carriedInCents < 0) breakdown.push(`−${euroCents(-carriedInCents)} over-assigned last month`);
  if (overspentDeductedCents > 0)
    breakdown.push(`−${euroCents(overspentDeductedCents)} for last month's uncovered overspending`);

  let state: { color: string; bg: string; copy: React.ReactNode; icon: string };
  if (toBeAssignedCents > 0) {
    state = {
      color: "var(--brand)",
      bg: "var(--violet-50)",
      copy: `${euroCents(toBeAssignedCents)} to assign`,
      icon: "wallet",
    };
  } else if (toBeAssignedCents === 0) {
    state = {
      color: "var(--mint-600)",
      bg: "var(--mint-50)",
      copy: "Every euro assigned",
      icon: "check",
    };
  } else {
    state = {
      color: "var(--expense)",
      bg: "var(--expense-soft)",
      copy: `−${euroCents(-toBeAssignedCents)} over — unassign somewhere`,
      icon: "trending-down",
    };
  }

  return (
    <div
      className="tba-hero"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        background: "var(--surface)",
        border: "1px solid var(--border-hairline)",
        borderRadius: "var(--r-xl)",
        padding: "16px 20px",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
        <span
          style={{
            width: 44,
            height: 44,
            flex: "none",
            borderRadius: "var(--r-md)",
            background: state.bg,
            color: state.color,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon name={state.icon} size={21} strokeWidth={2.25} />
        </span>
        <div
          style={{ minWidth: 0, cursor: onShowBreakdown ? "pointer" : undefined }}
          role={onShowBreakdown ? "button" : undefined}
          tabIndex={onShowBreakdown ? 0 : undefined}
          aria-label={onShowBreakdown ? "See where the money to assign comes from" : undefined}
          onClick={onShowBreakdown}
          onKeyDown={(e) => {
            if (onShowBreakdown && (e.key === "Enter" || e.key === " ")) {
              e.preventDefault();
              onShowBreakdown();
            }
          }}
        >
          <div className="ol-eyebrow" style={{ color: "var(--text-subtle)" }}>
            To be assigned
          </div>
          <div
            className="tba-hero-amount"
            style={{
              font: "800 26px var(--font-sans)",
              letterSpacing: "-0.9px",
              color: state.color,
              fontVariantNumeric: "tabular-nums",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {state.copy}
          </div>
          <div style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
            {income}
            {breakdown.map((part) => ` · ${part}`)}
          </div>
        </div>
      </div>
      {action && <div style={{ flex: "none" }}>{action}</div>}
    </div>
  );
}
