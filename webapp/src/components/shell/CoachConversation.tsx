"use client";

import React from "react";
import { BudgetBar } from "@/components/ui/BudgetBar";
import { Button } from "@/components/ui/Button";
import { CoachMessage } from "@/components/ui/CoachMessage";
import { CoachSuggestion } from "@/components/ui/CoachSuggestion";
import { Icon } from "@/components/ui/Icon";
import { IconButton } from "@/components/ui/IconButton";

interface Message {
  role: "coach" | "user";
  body: React.ReactNode;
}

const seed: Message[] = [
  {
    role: "coach",
    body: (
      <>
        Your dining spend is up <b>18%</b> this month — mostly weekend cafés.
      </>
    ),
  },
  {
    role: "coach",
    body: (
      <>
        <div style={{ marginBottom: 10 }}>Food &amp; dining vs budget:</div>
        <div style={{ background: "var(--bg)", borderRadius: "var(--r-md)", padding: 12 }}>
          <BudgetBar
            icon="coffee"
            tone="warning"
            label="Food & dining"
            spent="884 €"
            limit="900 €"
            percent={98}
          />
        </div>
      </>
    ),
  },
  { role: "user", body: "Can you cap it?" },
  {
    role: "coach",
    body: (
      <>
        Setting a <b>300 € monthly cap</b>. You&apos;re still on track for Japan 🎌
      </>
    ),
  },
];

export function CoachConversation() {
  const [msgs, setMsgs] = React.useState<Message[]>(seed);
  const [draft, setDraft] = React.useState("");
  const scroller = React.useRef<HTMLDivElement>(null);

  const send = (text: string) => {
    if (!text.trim()) return;
    setMsgs((m) => [
      ...m,
      { role: "user", body: text },
      {
        role: "coach",
        body: (
          <>
            Good question. Your biggest flexible spend is dining out — trimming
            60 €/week adds about <b>3.100 €</b> to savings this year. Want me to
            set a gentle limit?
          </>
        ),
      },
    ]);
    setDraft("");
  };

  React.useEffect(() => {
    if (scroller.current)
      scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [msgs]);

  return (
    <>
      <div
        ref={scroller}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "20px 18px",
          display: "flex",
          flexDirection: "column",
          gap: 14,
          minHeight: 0,
        }}
      >
        {msgs.map((m, i) => (
          <CoachMessage key={i} role={m.role}>
            {m.body}
          </CoachMessage>
        ))}
        <div style={{ paddingLeft: 40 }}>
          <Button variant="accent" size="sm" iconLeft="check">
            Set the 300 € cap
          </Button>
        </div>
      </div>

      <div
        style={{
          flex: "none",
          padding: "12px 16px 16px",
          borderTop: "1px solid var(--border-hairline)",
        }}
      >
        <div style={{ marginBottom: 12 }}>
          <CoachSuggestion
            suggestions={[
              { label: "Where can I cut back?", icon: "trending-down" },
              { label: "On track for Japan?", icon: "plane" },
            ]}
            onPick={setDraft}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              gap: 9,
              background: "var(--surface-sunk)",
              borderRadius: 999,
              padding: "0 16px",
              height: 46,
            }}
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") send(draft);
              }}
              placeholder="Ask the coach…"
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                background: "transparent",
                font: "500 14.5px var(--font-sans)",
                color: "var(--text-strong)",
                minWidth: 0,
              }}
            />
          </span>
          <IconButton
            icon="send"
            variant="fab"
            ariaLabel="Send"
            onClick={() => send(draft)}
            style={{ width: 46, height: 46 }}
          />
        </div>
      </div>
    </>
  );
}

export function CoachHeader({ note = "Watching your money" }: { note?: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: 20,
        borderBottom: "1px solid var(--border-hairline)",
      }}
    >
      <span
        style={{
          width: 40,
          height: 40,
          borderRadius: 999,
          background: "var(--grad-coach)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flex: "none",
        }}
      >
        <Icon name="sparkles" size={19} color="var(--mint-400)" />
      </span>
      <div style={{ flex: 1 }}>
        <div
          style={{
            font: "700 16px var(--font-sans)",
            letterSpacing: "-0.3px",
            color: "var(--text-strong)",
          }}
        >
          Coach
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            font: "500 12px var(--font-sans)",
            color: "var(--mint-600)",
          }}
        >
          <span style={{ width: 7, height: 7, borderRadius: 999, background: "var(--mint-500)" }} />{" "}
          {note}
        </div>
      </div>
      <IconButton icon="more-horizontal" variant="ghost" size="sm" ariaLabel="More" />
    </div>
  );
}
