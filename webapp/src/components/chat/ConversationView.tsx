"use client";

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { OnboardingNudge } from "@/components/home/OnboardingNudge";
import { Button } from "@/components/ui/Button";
import { ErrorPanel, SkeletonPanel } from "@/components/ui/QueryStates";
import {
  CoachUnavailableError,
  fetchConversation,
  fetchHome,
  sendCoachMessage,
  type ChatMessage,
  type ConversationView as ConversationPage,
} from "@/lib/api";
import { CoachBubble, DateSeparator, UserBubble, dayLabel, timeOf } from "./Bubbles";
import { Composer } from "./Composer";
import { ConversationContext, type ConversationActions } from "./ConversationContext";
import { SnapshotMessage } from "./SnapshotMessage";
import { WidgetRenderer } from "./WidgetRenderer";

/* Home as the conversation with Olmenta (spec: coach-conversation,
   conversation screen). The stored history, then the month snapshot as an
   unstored coach message, then what's said during this visit. Sending is
   idempotent by client id, so a retry never duplicates a message. */

const SCROLL_KEY = "olmenta.home.scroll";

const newClientId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

function merge(messages: ChatMessage[], extra: ChatMessage[]): ChatMessage[] {
  const byId = new Map(messages.map((m) => [m.id, m]));
  for (const m of extra) byId.set(m.id, m);
  return [...byId.values()].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
}

/** Plain text with the model's **bold**, newlines kept. */
function RichText({ text }: Readonly<{ text: string }>) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return (
    <p style={{ margin: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
      {parts.map((part, i) => (i % 2 === 1 ? <b key={i}>{part}</b> : <React.Fragment key={i}>{part}</React.Fragment>))}
    </p>
  );
}

function Message({ message }: Readonly<{ message: ChatMessage }>) {
  if (message.role === "user") {
    return <UserBubble text={message.text} time={timeOf(message.created_at)} />;
  }
  return (
    <CoachBubble time={timeOf(message.created_at)}>
      {message.text && <RichText text={message.text} />}
      {message.widgets.map((w, i) => (
        <WidgetRenderer key={`${w.type}-${i}`} widget={w} />
      ))}
    </CoachBubble>
  );
}

interface Pending {
  clientId: string;
  text: string;
  failed: boolean;
}

function readScroll(): number | null {
  try {
    const value = sessionStorage.getItem(SCROLL_KEY);
    return value === null ? null : Number(value);
  } catch {
    return null;
  }
}

function writeScroll(top: number): void {
  try {
    sessionStorage.setItem(SCROLL_KEY, String(Math.round(top)));
  } catch {
    /* no storage: the position just isn't restored */
  }
}

export function ConversationView() {
  const queryClient = useQueryClient();
  const home = useQuery({ queryKey: ["home"], queryFn: fetchHome });
  const conversation = useQuery({ queryKey: ["coach-conversation"], queryFn: () => fetchConversation() });
  const [older, setOlder] = React.useState<ChatMessage[]>([]);
  const [olderHasMore, setOlderHasMore] = React.useState<boolean | null>(null);
  const [loadingOlder, setLoadingOlder] = React.useState(false);
  const [pending, setPending] = React.useState<Pending[]>([]);
  const [unavailable, setUnavailable] = React.useState<{ clientId: string; text: string } | null>(null);
  const [staleReplacements, setStaleReplacements] = React.useState<Set<string>>(() => new Set());
  // Messages present when Home opened (and older pages) sit above the snapshot.
  const [baseline, setBaseline] = React.useState<Set<string> | null>(null);
  const scroller = React.useRef<HTMLDivElement>(null);
  const stickToBottom = React.useRef(false);
  const restored = React.useRef(false);
  const prependFrom = React.useRef<number | null>(null);

  if (conversation.data && baseline === null) {
    setBaseline(new Set(conversation.data.messages.map((m) => m.id)));
  }

  const send = useMutation({
    mutationFn: (p: { text: string; clientId: string }) => sendCoachMessage(p.text, p.clientId),
    onSuccess: (pair, p) => {
      queryClient.setQueryData<ConversationPage>(["coach-conversation"], (old) => ({
        messages: merge(old?.messages ?? [], [pair.user_message, pair.reply]),
        has_more: old?.has_more ?? false,
      }));
      setPending((list) => list.filter((x) => x.clientId !== p.clientId));
      stickToBottom.current = true;
    },
    onError: (error, p) => {
      if (error instanceof CoachUnavailableError && error.userMessage) {
        const kept = error.userMessage;
        queryClient.setQueryData<ConversationPage>(["coach-conversation"], (old) => ({
          messages: merge(old?.messages ?? [], [kept]),
          has_more: old?.has_more ?? false,
        }));
        setPending((list) => list.filter((x) => x.clientId !== p.clientId));
      } else {
        setPending((list) => list.map((x) => (x.clientId === p.clientId ? { ...x, failed: true } : x)));
      }
      setUnavailable(p);
      stickToBottom.current = true;
    },
  });

  const ask = React.useCallback(
    (text: string, clientId: string = newClientId()) => {
      setUnavailable(null);
      setPending((list) => [...list.filter((x) => x.clientId !== clientId), { clientId, text, failed: false }]);
      stickToBottom.current = true;
      send.mutate({ text, clientId });
    },
    [send],
  );

  const actions = React.useMemo<ConversationActions>(
    () => ({
      ask: (text) => ask(text),
      markStale: (id) => setStaleReplacements((s) => new Set(s).add(id)),
      isStaleReplacement: (id) => staleReplacements.has(id),
    }),
    [ask, staleReplacements],
  );

  const loadOlder = async () => {
    const all = merge(older, conversation.data?.messages ?? []);
    if (!all.length || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const page = await fetchConversation(all[0].id);
      setBaseline((b) => new Set([...(b ?? []), ...page.messages.map((m) => m.id)]));
      prependFrom.current = scroller.current?.scrollHeight ?? null;
      setOlder((o) => merge(o, page.messages));
      setOlderHasMore(page.has_more);
    } finally {
      setLoadingOlder(false);
    }
  };

  const messages = merge(older, conversation.data?.messages ?? []);
  const known = baseline ?? new Set<string>();
  const before = messages.filter((m) => known.has(m.id));
  const after = messages.filter((m) => !known.has(m.id));
  const hasMore = olderHasMore ?? conversation.data?.has_more ?? false;
  const ready = Boolean(home.data && conversation.data && baseline);

  // Scroll: restore the last position on return, else start at the bottom;
  // follow new messages; keep the view still when older ones are prepended.
  React.useLayoutEffect(() => {
    const el = scroller.current;
    if (!el || !ready) return;
    if (!restored.current) {
      restored.current = true;
      const saved = readScroll();
      el.scrollTop = saved ?? el.scrollHeight;
      return;
    }
    if (prependFrom.current !== null) {
      el.scrollTop += el.scrollHeight - prependFrom.current;
      prependFrom.current = null;
    } else if (stickToBottom.current) {
      el.scrollTop = el.scrollHeight;
      stickToBottom.current = false;
    }
  });

  const timeline: React.ReactNode[] = [];
  let lastDay = "";
  const separate = (iso: string, key: string) => {
    const label = dayLabel(iso);
    if (label !== lastDay) {
      timeline.push(<DateSeparator key={`sep-${key}`} label={label} />);
      lastDay = label;
    }
  };
  for (const m of before) {
    separate(m.created_at, m.id);
    timeline.push(<Message key={m.id} message={m} />);
  }
  if (home.data) {
    separate(home.data.generated_at, "snapshot");
    timeline.push(<SnapshotMessage key="snapshot" home={home.data} />);
  }
  for (const m of after) {
    separate(m.created_at, m.id);
    timeline.push(<Message key={m.id} message={m} />);
  }
  for (const p of pending) {
    timeline.push(<UserBubble key={`pending-${p.clientId}`} text={p.text} status={p.failed ? "failed" : "sending"} />);
  }

  return (
    <ConversationContext.Provider value={actions}>
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
        <div
          ref={scroller}
          data-testid="conversation"
          onScroll={(e) => writeScroll(e.currentTarget.scrollTop)}
          style={{ flex: 1, minHeight: 0, overflowY: "auto" }}
        >
          <div style={{ maxWidth: 1040, margin: "0 auto", padding: "16px 24px 24px", display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Before setup the snapshot itself is the invitation. */}
            {home.data?.status !== "not_set_up" && <OnboardingNudge />}
            {hasMore && (
              <Button variant="ghost" size="sm" onClick={loadOlder} disabled={loadingOlder} style={{ alignSelf: "center" }}>
                {loadingOlder ? "Loading…" : "Show earlier messages"}
              </Button>
            )}
            {home.isError || conversation.isError ? (
              <ErrorPanel
                message="We couldn't load your conversation."
                onRetry={() => {
                  home.refetch();
                  conversation.refetch();
                }}
              />
            ) : !ready ? (
              <>
                <SkeletonPanel rows={2} rowHeight={40} />
                <SkeletonPanel rows={3} rowHeight={36} />
              </>
            ) : (
              timeline
            )}
            {send.isPending && (
              <div role="status" data-testid="coach-answering" style={{ font: "500 14px var(--font-sans)", color: "var(--text-muted)", paddingLeft: 52 }}>
                Olmenta is answering…
              </div>
            )}
            {unavailable && !send.isPending && (
              <div
                role="alert"
                data-testid="coach-unavailable"
                style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", background: "var(--warning-soft)", borderRadius: "var(--r-md)", padding: "10px 14px", font: "500 14px var(--font-sans)", color: "#8A5300" }}
              >
                <span style={{ flex: 1, minWidth: 220 }}>
                  The coach can&apos;t answer right now. Your message is kept, and everything else on Home still works.
                </span>
                <Button size="sm" variant="secondary" onClick={() => ask(unavailable.text, unavailable.clientId)}>
                  Try again
                </Button>
              </div>
            )}
          </div>
        </div>
        <Composer onSend={(text) => ask(text)} busy={send.isPending} />
      </div>
    </ConversationContext.Provider>
  );
}
