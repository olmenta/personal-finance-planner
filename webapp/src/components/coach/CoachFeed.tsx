"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { fetchCoachProposals, type CoachProposal } from "@/lib/api";
import { euroCents } from "@/lib/format";
import { useProposalActions } from "./useProposalActions";

/* Coach feed (spec: coach-proposals): real proposals instead of a scripted
   chat. Three visible, "See more (N)" for the rest. */

export const VISIBLE_PROPOSALS = 3;

export function ProposalCard({ p }: Readonly<{ p: CoachProposal }>) {
  const { primary, secondary, notNow, sources, takeFrom, error, dialogs } = useProposalActions(p);
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

export function CoachFeed() {
  const query = useQuery({ queryKey: ["coach-proposals"], queryFn: fetchCoachProposals });
  const [showAll, setShowAll] = React.useState(false);
  const proposals = query.data?.proposals ?? [];
  const shown = showAll ? proposals : proposals.slice(0, VISIBLE_PROPOSALS);
  const hidden = proposals.length - shown.length;

  return (
    <div
      data-testid="coach-feed"
      style={{ flex: 1, overflowY: "auto", minHeight: 0, padding: 16, display: "flex", flexDirection: "column", gap: 10 }}
    >
      {query.isPending ? (
        <div style={{ font: "500 13.5px var(--font-sans)", color: "var(--text-muted)" }}>Looking at your plan…</div>
      ) : proposals.length === 0 ? (
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start", font: "500 14px/1.5 var(--font-sans)", color: "var(--text-body)" }}>
          <Icon name="check-circle" size={18} color="var(--accent)" />
          <span>Your plan looks on track. I&apos;ll speak up when something needs you.</span>
        </div>
      ) : (
        <>
          {shown.map((p) => (
            <ProposalCard key={p.fingerprint} p={p} />
          ))}
          {hidden > 0 && (
            <Button variant="ghost" size="sm" onClick={() => setShowAll(true)}>
              See more ({hidden})
            </Button>
          )}
        </>
      )}
    </div>
  );
}

/* Dashboard: the most urgent proposal as one coach capsule (spec:
   coach-proposals, dashboard coach capsule). */
export function CoachTopCapsule() {
  const query = useQuery({ queryKey: ["coach-proposals"], queryFn: fetchCoachProposals });
  const top = query.data?.proposals[0];
  if (!top) return null;
  return <TopCapsule key={top.fingerprint} p={top} />;
}

function TopCapsule({ p }: Readonly<{ p: CoachProposal }>) {
  const { primary, secondary, notNow, sources, takeFrom, dialogs } = useProposalActions(p);
  return (
    <div data-testid="coach-capsule" style={{ marginBottom: 16, display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexWrap: "wrap",
          background: "var(--grad-coach)",
          color: "#fff",
          borderRadius: "var(--r-xl)",
          padding: "12px 14px",
          boxShadow: "var(--shadow-coach)",
        }}
      >
        <Icon name="sparkles" size={16} color="var(--mint-400)" />
        <div style={{ flex: "1 1 260px", minWidth: 0 }}>
          <div style={{ font: "600 14.5px var(--font-sans)" }}>{p.title}</div>
          <div style={{ font: "500 13px/1.45 var(--font-sans)", color: "rgba(255,255,255,.8)" }}>{p.body}</div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {primary && !sources && (
            <Button variant="accent" size="sm" onClick={primary.run} disabled={primary.pending}>
              {primary.label}
            </Button>
          )}
          {secondary && !sources && (
            <Button variant="secondary" size="sm" onClick={secondary.run}>
              {secondary.label}
            </Button>
          )}
          {sources?.map((s) => (
            <Button key={s.category_id} variant="secondary" size="sm" onClick={() => takeFrom(s.category_id)}>
              From {s.name}
            </Button>
          ))}
          <button
            onClick={notNow.run}
            disabled={notNow.pending}
            style={{ border: "none", background: "transparent", cursor: "pointer", color: "rgba(255,255,255,.75)", font: "600 13px var(--font-sans)", padding: "6px 4px" }}
          >
            Not now
          </button>
        </div>
      </div>
      {dialogs}
    </div>
  );
}
