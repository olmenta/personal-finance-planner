"use client";

import Link from "next/link";
import React from "react";
import {
  HomeHeaderLine,
  MonthWidget,
  NoAccounts,
  PriorityAction,
  RecommendationGroups,
  coachLine,
  futureSentence,
  reasonList,
} from "@/components/home/HomeWidgets";
import type { HomeView } from "@/lib/api";
import { euroCents } from "@/lib/format";
import { monthLabel } from "@/lib/schedules";
import { CoachBubble, timeOf } from "./Bubbles";

/* The month as a coach message (spec: coach-conversation, conversation
   screen). Shown on every visit, never stored. Deterministic sentences from
   GET /home: no model is involved, so it works when the AI doesn't. */

const link: React.CSSProperties = {
  border: "none",
  background: "none",
  padding: 0,
  cursor: "pointer",
  font: "500 15px var(--font-sans)",
  color: "var(--brand)",
  textDecoration: "underline",
  textUnderlineOffset: 3,
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  alignSelf: "flex-start",
};

export function SnapshotMessage({ home }: Readonly<{ home: HomeView }>) {
  const [split, setSplit] = React.useState(false);
  const [more, setMore] = React.useState(false);
  const time = timeOf(home.generated_at);
  if (home.status === "no_accounts") {
    return (
      <CoachBubble time={time} testId="snapshot-message">
        <NoAccounts />
      </CoachBubble>
    );
  }
  const s = home.summary;
  const setAside = s.covered_cents + s.saved_cents;
  const month = monthLabel(home.month).split(" ")[0];
  const uncovered = home.reasons.some((r) => r.code === "uncovered_payments");
  const future = futureSentence(home);
  const suggestions = home.groups.reduce((n, g) => n + g.proposals.length, 0);

  return (
    <CoachBubble time={time} testId="snapshot-message">
      <p style={{ margin: 0 }}>
        I&apos;ve updated your month. You have <b>{euroCents(s.accounts_cents)}</b> in your accounts
        {setAside > 0 ? (
          <>; <b>{euroCents(setAside)}</b> of it is already set aside for payments and savings.</>
        ) : (
          "."
        )}
      </p>
      <button type="button" style={link} aria-expanded={split} onClick={() => setSplit((o) => !o)}>
        {split ? "Hide how it's split" : "View how it's split"} <span aria-hidden>›</span>
      </button>
      {split && <MonthWidget home={home} breakdownOpen />}
      <div data-testid="coach-line" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <p style={{ margin: 0 }}>{coachLine(home)}</p>
        {home.status === "needs_organizing" && home.reasons.length > 0 && reasonList(home.reasons)}
      </div>
      <p style={{ margin: 0 }} data-testid="future-line">
        {s.still_to_pay_cents > 0 && !uncovered && `${month}'s payments are covered. `}
        <b>{future.lead}</b> {future.text}{" "}
        <Link href={future.link.href} style={{ color: "var(--brand)", fontWeight: 600 }}>
          {future.link.label}
        </Link>
      </p>
      <PriorityAction home={home} />
      {suggestions > 0 &&
        (more ? (
          <RecommendationGroups home={home} />
        ) : (
          <button type="button" style={link} onClick={() => setMore(true)}>
            {suggestions === 1 ? "1 more suggestion" : `${suggestions} more suggestions`} <span aria-hidden>›</span>
          </button>
        ))}
      <HomeHeaderLine home={home} />
    </CoachBubble>
  );
}
