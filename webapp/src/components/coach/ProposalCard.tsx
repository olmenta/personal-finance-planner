"use client";

import { Button } from "@/components/ui/Button";
import { type CoachProposal } from "@/lib/api";
import { euroCents } from "@/lib/format";
import { useProposalActions } from "./useProposalActions";

/* One coach proposal with its action and "Not now" (spec: coach-proposals).
   Home shows it as the priority action and inside recommendation groups. */

export function ProposalCard({ p: shown }: Readonly<{ p: CoachProposal }>) {
  const { proposal: p, primary, secondary, notNow, sources, takeFrom, error, dialogs } =
    useProposalActions(shown);
  return (
    <div
      data-testid="coach-proposal"
      style={{
        background: "var(--surface-sunk)",
        borderRadius: "var(--r-lg)",
        padding: "14px 14px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ font: "600 14.5px var(--font-sans)", color: "var(--text-strong)", letterSpacing: "-0.1px" }}>
        {p.title}
      </div>
      <div style={{ font: "500 13.5px/1.5 var(--font-sans)", color: "var(--text-body)" }}>{p.body}</div>
      {sources ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
            There isn&apos;t {euroCents(p.diff_cents ?? 0)} left to assign. Take it from:
          </span>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {sources.map((s) => (
              <Button key={s.category_id} variant="secondary" size="sm" onClick={() => takeFrom(s.category_id)}>
                {s.name} · {euroCents(s.available_cents)}
              </Button>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {primary && (
            <Button variant="accent" size="sm" onClick={primary.run} disabled={primary.pending}>
              {primary.label}
            </Button>
          )}
          {secondary && (
            <Button variant="secondary" size="sm" onClick={secondary.run}>
              {secondary.label}
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={notNow.run} disabled={notNow.pending}>
            {notNow.label}
          </Button>
        </div>
      )}
      {error && (
        <div role="alert" style={{ font: "600 12.5px var(--font-sans)", color: "var(--expense)" }}>{error}</div>
      )}
      {dialogs}
    </div>
  );
}
