"use client";

import React from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { createCoachAction, type CoachAction, type FuturePaymentData } from "@/lib/api";
import { euroCents } from "@/lib/format";
import { monthLabel } from "@/lib/schedules";
import { ActionPreview, actionError } from "./Actions";
import { useConversationActions } from "./ConversationContext";

/* A future payment and what it takes to make it (mockup: the car insurance
   card). Every figure comes from the schedule engine. "Review adjustment"
   only opens a preview: the budget changes when the user confirms it. */

const whole = (cents: number) => euroCents(cents, cents % 100 === 0 ? 0 : 2);

export function FuturePaymentCard({ data: p }: Readonly<{ data: FuturePaymentData }>) {
  const { ask } = useConversationActions();
  const [review, setReview] = React.useState<CoachAction | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const adjust = useMutation({
    mutationFn: () =>
      createCoachAction({
        kind: "moves",
        moves: [{ from_category_id: null, to_category_id: p.category_id, amount_cents: p.gap_cents }],
      }),
    onSuccess: (a) => {
      setError(null);
      setReview(a);
    },
    onError: (e) => setError(actionError(e)),
  });
  const label: React.CSSProperties = { font: "500 13.5px var(--font-sans)", color: "var(--text-muted)" };
  const figure: React.CSSProperties = { font: "700 16px var(--font-sans)", color: "var(--text-strong)", fontVariantNumeric: "tabular-nums" };

  return (
    <div
      data-testid="future-payment"
      style={{ border: "1px solid var(--border-hairline)", borderRadius: "var(--r-lg)", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}
    >
      <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
        <span style={{ width: 44, height: 44, borderRadius: "var(--r-full)", background: "var(--violet-50)", display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          <Icon name={p.icon} size={20} color="var(--violet-700)" />
        </span>
        <div>
          <div style={{ font: "700 16.5px var(--font-sans)", color: "var(--text-strong)" }}>{p.name}</div>
          <div style={label}>{monthLabel(p.due_month)}</div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", font: "500 14px var(--font-sans)", color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>
          <span>
            <b style={{ color: "var(--text-strong)" }}>{whole(p.saved_cents)} saved</b> of {whole(p.target_cents)}
          </span>
          <span>{p.percent}%</span>
        </div>
        <div role="progressbar" aria-valuenow={p.percent} aria-valuemin={0} aria-valuemax={100} aria-label={`${p.name} saved`}
          style={{ height: 10, borderRadius: 999, background: "var(--surface-sunk)", overflow: "hidden" }}>
          <div style={{ width: `${p.percent}%`, height: "100%", background: "var(--brand)", borderRadius: 999 }} />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 12, paddingBottom: 10, borderBottom: "1px solid var(--border-hairline)" }}>
        <div>
          <div style={label}>Current plan</div>
          <div style={figure}>{whole(p.plan_monthly_cents)}/month</div>
        </div>
        <Icon name="arrow-right" size={18} color="var(--text-muted)" />
        <div>
          <div style={label}>To make it</div>
          <div style={figure}>{whole(p.needed_monthly_cents)}/month</div>
        </div>
      </div>
      <div style={label}>
        {p.contributions_left === 1
          ? `1 contribution of ${whole(p.needed_monthly_cents)}.`
          : `${p.contributions_left} contributions of ${whole(p.needed_monthly_cents)}.`}
        {p.on_track && " Your current plan gets you there."}
      </div>

      {review ? (
        <ActionPreview action={review} />
      ) : (
        <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          {p.gap_cents > 0 && (
            <Button onClick={() => adjust.mutate()} disabled={adjust.isPending} style={{ minWidth: 200 }}>
              Review adjustment
            </Button>
          )}
          <button
            type="button"
            onClick={() => ask(`What other options do I have for ${p.name}?`)}
            style={{ border: "none", background: "none", cursor: "pointer", font: "600 14.5px var(--font-sans)", color: "var(--brand)", padding: 0 }}
          >
            See other options
          </button>
        </div>
      )}
      {error && <div role="alert" style={{ font: "600 13px var(--font-sans)", color: "var(--expense)" }}>{error}</div>}
      <div style={{ display: "flex", gap: 8, alignItems: "center", font: "500 13px var(--font-sans)", color: "var(--text-muted)" }}>
        <Icon name="info" size={15} />
        Reviewing doesn&apos;t change your budget.
      </div>
    </div>
  );
}
