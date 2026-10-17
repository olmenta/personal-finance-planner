"use client";

import { ProposalCard } from "@/components/coach/ProposalCard";
import { Breakdown, MonthWidget } from "@/components/home/HomeWidgets";
import type { CoachWidget } from "@/lib/api";
import { euroCents } from "@/lib/format";
import { ActionPreview, ActionResult } from "./Actions";
import { CategoryChoice } from "./CategoryChoice";
import { FuturePaymentCard } from "./FuturePaymentCard";

/* The widget catalog (spec: coach-conversation). The server already dropped
   unknown types; anything this build doesn't know renders nothing. */
export function WidgetRenderer({ widget }: Readonly<{ widget: CoachWidget }>) {
  switch (widget.type) {
    case "month_summary":
      return <MonthWidget home={widget.data} />;
    case "breakdown":
      return <Breakdown summary={widget.data.summary} />;
    case "future_payment":
      return <FuturePaymentCard data={widget.data} />;
    case "action_preview":
      return <ActionPreview action={widget.data.action} />;
    case "action_result":
      return <ActionResult action={widget.data.action} />;
    case "category_choice":
      return <CategoryChoice action={widget.data.action} />;
    case "coach_proposal":
      return <ProposalCard p={widget.data} />;
    case "transaction": {
      const t = widget.data;
      return (
        <div data-testid="transaction-widget" style={{ display: "flex", justifyContent: "space-between", gap: 12, font: "500 14px var(--font-sans)", color: "var(--text-body)", fontVariantNumeric: "tabular-nums" }}>
          <span>
            {new Date(t.date).toLocaleDateString("es-ES")} · {t.payee ?? t.description ?? "Transaction"}
            {t.category_name ? ` · ${t.category_name}` : ""}
          </span>
          <b style={{ color: t.amount_cents > 0 ? "var(--income)" : "var(--text-strong)" }}>{euroCents(t.amount_cents)}</b>
        </div>
      );
    }
    default:
      return null;
  }
}
