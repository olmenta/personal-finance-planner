"use client";

import React from "react";
import { AddTransactionDialog } from "@/components/AddTransactionDialog";
import { Icon } from "@/components/ui/Icon";

/* The composer (mockup): "+" opens the add-transaction form, the field asks
   or records, send. The draft survives leaving Home (localStorage; a
   storage failure just means no draft). */

const DRAFT_KEY = "olmenta.coach.draft";

function readDraft(): string {
  try {
    return localStorage.getItem(DRAFT_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeDraft(text: string): void {
  try {
    if (text) localStorage.setItem(DRAFT_KEY, text);
    else localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* private mode or blocked storage: the draft just isn't kept */
  }
}

export interface ComposerProps {
  onSend: (text: string) => void;
  busy: boolean;
}

export function Composer({ onSend, busy }: Readonly<ComposerProps>) {
  const [text, setText] = React.useState("");
  const [adding, setAdding] = React.useState(false);
  React.useEffect(() => {
    // A draft handed over in the URL (e.g. from What you owe) fills an empty
    // field without sending; a draft the user was writing wins.
    let initial = readDraft();
    try {
      const url = new URL(window.location.href);
      const handed = url.searchParams.get("draft");
      if (handed) {
        if (!initial) {
          initial = handed;
          writeDraft(handed);
        }
        url.searchParams.delete("draft");
        window.history.replaceState(null, "", url.pathname + url.search + url.hash);
      }
    } catch {
      /* no URL access: keep the stored draft */
    }
    setText(initial);
  }, []);
  const update = (value: string) => {
    setText(value);
    writeDraft(value);
  };
  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    onSend(trimmed);
    update("");
  };
  const round: React.CSSProperties = {
    width: 46,
    height: 46,
    flex: "none",
    borderRadius: "var(--r-full)",
    border: "none",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    transition: "transform var(--dur-fast) var(--ease-spring), background var(--dur-base) var(--ease-out)",
  };
  return (
    <div style={{ borderTop: "1px solid var(--border-hairline)", background: "var(--surface)", padding: "12px 16px 8px" }}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        style={{ display: "flex", gap: 12, alignItems: "center", maxWidth: 1040, margin: "0 auto" }}
      >
        <button type="button" aria-label="Add transaction" onClick={() => setAdding(true)}
          style={{ ...round, background: "var(--violet-50)", color: "var(--brand)" }}>
          <Icon name="plus" size={22} />
        </button>
        <textarea
          data-testid="composer-input"
          aria-label="Ask or record an expense"
          placeholder="Ask or record an expense…"
          rows={1}
          value={text}
          onChange={(e) => update(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          style={{
            flex: 1,
            minWidth: 0,
            resize: "none",
            border: "1px solid var(--border-hairline)",
            borderRadius: 999,
            padding: "12px 20px",
            font: "500 15.5px/1.4 var(--font-sans)",
            color: "var(--text-strong)",
            background: "var(--surface)",
            outline: "none",
          }}
        />
        <button type="submit" aria-label="Send" disabled={busy || !text.trim()}
          style={{ ...round, background: "var(--brand)", color: "#fff", opacity: busy || !text.trim() ? 0.6 : 1 }}>
          <Icon name="send" size={20} />
        </button>
      </form>
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 6, marginTop: 6, font: "500 12.5px var(--font-sans)", color: "var(--text-muted)" }}>
        <Icon name="clock" size={13} />
        Your history is kept
      </div>
      <AddTransactionDialog open={adding} onOpenChange={setAdding} />
    </div>
  );
}
