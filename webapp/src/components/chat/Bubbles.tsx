import React from "react";
import { Icon } from "@/components/ui/Icon";

/* Conversation bubbles (spec: coach-conversation, mockup redesign.png): the
   coach on the left behind its mint sparkle avatar, the user on the right in
   soft violet with the time. */

export const timeOf = (iso: string) =>
  new Date(iso).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });

export function CoachAvatar() {
  return (
    <span
      aria-hidden
      style={{
        width: 40,
        height: 40,
        flex: "none",
        borderRadius: "var(--r-full)",
        background: "var(--mint-50)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Icon name="sparkles" size={19} color="var(--accent)" strokeWidth={2.2} />
    </span>
  );
}

export interface CoachBubbleProps {
  time?: string;
  children: React.ReactNode;
  testId?: string;
}

export function CoachBubble({ time, children, testId = "coach-message" }: Readonly<CoachBubbleProps>) {
  return (
    <div data-testid={testId} data-role="assistant" style={{ display: "flex", gap: 12, alignItems: "flex-start", maxWidth: 720 }}>
      <CoachAvatar />
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{ font: "600 13.5px var(--font-sans)", color: "var(--text-body)" }}>
          Olmenta
          {time && <span style={{ fontWeight: 500, color: "var(--text-muted)" }}> · {time}</span>}
        </div>
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border-hairline)",
            borderRadius: "var(--r-lg)",
            boxShadow: "var(--shadow-xs)",
            padding: "14px 18px",
            display: "flex",
            flexDirection: "column",
            gap: 12,
            font: "500 15px/1.5 var(--font-sans)",
            color: "var(--text-strong)",
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

export interface UserBubbleProps {
  text: string;
  time?: string;
  status?: "sending" | "sent" | "failed";
}

export function UserBubble({ text, time, status = "sent" }: Readonly<UserBubbleProps>) {
  return (
    <div data-testid="user-message" data-role="user" style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10 }}>
      <div
        style={{
          maxWidth: "min(560px, 78%)",
          background: "var(--brand-soft)",
          color: "var(--text-strong)",
          borderRadius: "var(--r-lg)",
          padding: "12px 18px",
          font: "500 15.5px/1.45 var(--font-sans)",
          whiteSpace: "pre-wrap",
          overflowWrap: "anywhere",
        }}
      >
        {text}
      </div>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 4, font: "500 12.5px var(--font-sans)", color: "var(--text-muted)", flex: "none" }}>
        {status === "sending" ? "Sending…" : status === "failed" ? "Not sent" : time}
        {status === "sent" && <Icon name="check" size={14} color="var(--brand)" />}
      </span>
    </div>
  );
}

export function DateSeparator({ label }: Readonly<{ label: string }>) {
  return (
    <div role="separator" aria-label={label} style={{ display: "flex", alignItems: "center", gap: 12, margin: "4px 0" }}>
      <span style={{ flex: 1, height: 1, background: "var(--border-hairline)" }} />
      <span
        style={{
          font: "500 13px var(--font-sans)",
          color: "var(--text-body)",
          border: "1px solid var(--border-hairline)",
          background: "var(--surface)",
          borderRadius: 999,
          padding: "6px 14px",
        }}
      >
        {label}
      </span>
      <span style={{ flex: 1, height: 1, background: "var(--border-hairline)" }} />
    </div>
  );
}

/** "Today · 14 October 2026", "Yesterday · …", or the date. */
export function dayLabel(iso: string, now: Date = new Date()): string {
  const day = new Date(iso);
  const date = day.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  const key = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (key(day) === key(now)) return `Today · ${date}`;
  if (key(day) === key(yesterday)) return `Yesterday · ${date}`;
  return date;
}
