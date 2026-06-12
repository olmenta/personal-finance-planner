"use client";

import { useRouter } from "next/navigation";
import React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { CoachMessage } from "@/components/ui/CoachMessage";
import { Icon } from "@/components/ui/Icon";
import { Input } from "@/components/ui/Input";
import {
  ApiError,
  fetchOnboardingSession,
  finalizeOnboarding,
  sendOnboardingMessage,
  startOnboarding,
  useOnboardingTemplate,
  type OnboardingFinalizePayload,
  type OnboardingSessionView,
  type OnboardingTranscriptEntry,
} from "@/lib/api";
import { ReviewScreen } from "./ReviewScreen";

/* Full-screen AI onboarding interview (spec: ai-onboarding). Outside the app
   shell on purpose: no sidebar, no nav — one conversation, then one review. */

function TypingIndicator() {
  return (
    <CoachMessage>
      <span style={{ color: "var(--text-muted)" }}>…</span>
    </CoachMessage>
  );
}

function QuickInputs({
  entry,
  disabled,
  onSend,
}: Readonly<{
  entry: OnboardingTranscriptEntry;
  disabled: boolean;
  onSend: (message: string) => void;
}>) {
  const [selected, setSelected] = React.useState<string[]>([]);
  const [text, setText] = React.useState("");
  const kind = entry.input_kind ?? "text";

  // One answer can be ticked options, free text, or both ("Netflix, Spotify,
  // y también Google One") — the model reads it as a single reply.
  const combined = [...selected, text.trim()].filter(Boolean).join(", ");
  const sendCombined = () => {
    if (!combined) return;
    onSend(combined);
    setSelected([]);
    setText("");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {kind === "chips" && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {(entry.options ?? []).map((option) => (
            <Button
              key={option}
              variant="secondary"
              size="sm"
              disabled={disabled}
              onClick={() => onSend(option)}
            >
              {option}
            </Button>
          ))}
        </div>
      )}
      {kind === "checkboxes" && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {(entry.options ?? []).map((option) => {
            const active = selected.includes(option);
            return (
              <Button
                key={option}
                variant={active ? "primary" : "secondary"}
                size="sm"
                disabled={disabled}
                iconLeft={active ? "check" : undefined}
                onClick={() =>
                  setSelected((prev) =>
                    active ? prev.filter((o) => o !== option) : [...prev, option],
                  )
                }
              >
                {option}
              </Button>
            );
          })}
        </div>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          sendCombined();
        }}
        style={{ display: "flex", gap: 8 }}
      >
        <Input
          value={text}
          onChange={(event) => setText(event.target.value)}
          disabled={disabled}
          placeholder={
            kind === "money"
              ? "e.g. 2.400 €"
              : kind === "checkboxes"
                ? selected.length > 0
                  ? "Add anything else…"
                  : "Pick options or type your answer…"
                : "Type your answer…"
          }
          inputMode={kind === "money" ? "decimal" : undefined}
          wrapStyle={{ flex: 1 }}
        />
        <Button type="submit" disabled={disabled || !combined} iconLeft="arrow-up">
          Send
        </Button>
      </form>
    </div>
  );
}

function UnavailableScreen({
  onTemplate,
  submitting,
}: Readonly<{ onTemplate: () => void; submitting: boolean }>) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, textAlign: "center" }}>
      <Icon name="cloud-off" size={34} color="var(--text-subtle)" style={{ margin: "0 auto" }} />
      <p style={{ font: "600 16px var(--font-sans)", color: "var(--text-strong)", margin: 0 }}>
        The interview isn&apos;t available right now
      </p>
      <p style={{ font: "500 14px var(--font-sans)", color: "var(--text-muted)", margin: 0 }}>
        Start with our starter categories — you can rename or replace them any time.
      </p>
      <Button size="lg" disabled={submitting} onClick={onTemplate}>
        {submitting ? "Setting up…" : "Use the starter template"}
      </Button>
    </div>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [session, setSession] = React.useState<OnboardingSessionView | null>(null);
  const [unavailable, setUnavailable] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  // Survives StrictMode's dev mount→cleanup→mount cycle: without it the
  // effect fires twice and races two POST /onboarding/start calls.
  const bootRef = React.useRef(false);

  React.useEffect(() => {
    if (bootRef.current) return;
    bootRef.current = true;
    (async () => {
      try {
        // Resume an interview in flight; start a fresh one otherwise.
        const existing = await fetchOnboardingSession().catch((error: unknown) => {
          if (error instanceof ApiError && error.status === 404) return null;
          throw error;
        });
        setSession(existing ?? (await startOnboarding()));
      } catch (error) {
        if (error instanceof ApiError && error.status === 503) {
          setUnavailable(true);
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const send = useMutation({
    mutationFn: sendOnboardingMessage,
    onSuccess: setSession,
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.status === 503) setUnavailable(true);
    },
  });

  const finishedSetup = () => {
    queryClient.invalidateQueries();
    router.push("/");
  };

  const finalize = useMutation({
    mutationFn: (payload: OnboardingFinalizePayload) =>
      finalizeOnboarding(session!.id, payload),
    onSuccess: finishedSetup,
  });

  const template = useMutation({
    mutationFn: useOnboardingTemplate,
    onSuccess: finishedSetup,
  });

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [session?.transcript.length, send.isPending]);

  const lastEntry = session?.transcript.at(-1);
  const interviewDone = Boolean(lastEntry?.done && session?.proposal);

  return (
    <main
      style={{
        minHeight: "100dvh",
        background: "var(--bg-app)",
        display: "flex",
        justifyContent: "center",
        padding: "24px 16px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 640,
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        <header style={{ textAlign: "center" }}>
          <span className="ol-eyebrow" style={{ color: "var(--brand)" }}>
            Welcome to Olmenta
          </span>
          <h1
            style={{
              font: "800 24px/1.2 var(--font-sans)",
              letterSpacing: "-0.5px",
              color: "var(--text-strong)",
              margin: "6px 0 0",
            }}
          >
            {interviewDone ? "Review your setup" : "Let's set up your budget"}
          </h1>
        </header>

        {loading && <TypingIndicator />}

        {!loading && unavailable && (
          <UnavailableScreen
            onTemplate={() => template.mutate()}
            submitting={template.isPending}
          />
        )}

        {!loading && !unavailable && session && !interviewDone && (
          <>
            <div
              ref={scrollRef}
              style={{
                flex: 1,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: 12,
                paddingBottom: 8,
              }}
            >
              {session.transcript.map((entry, index) => (
                <CoachMessage
                  key={`turn-${index}`}
                  role={entry.role === "assistant" ? "coach" : "user"}
                >
                  {entry.content}
                </CoachMessage>
              ))}
              {send.isPending && <TypingIndicator />}
            </div>
            {lastEntry?.role === "assistant" && !lastEntry.done && (
              <QuickInputs
                entry={lastEntry}
                disabled={send.isPending}
                onSend={(message) => send.mutate(message)}
              />
            )}
          </>
        )}

        {!loading && !unavailable && session && interviewDone && session.proposal && (
          <ReviewScreen
            proposal={session.proposal}
            submitting={finalize.isPending}
            onConfirm={(payload) => finalize.mutate(payload)}
          />
        )}
      </div>
    </main>
  );
}
