"use client";

import { useRouter } from "next/navigation";
import React from "react";
import { useQuery } from "@tanstack/react-query";
import { CoachCapsule } from "@/components/ui/CoachCapsule";
import { Icon } from "@/components/ui/Icon";
import { fetchOnboardingStatus } from "@/lib/api";

const ONBOARDING_DISMISSED_KEY = "olmenta-onboarding-nudge-dismissed";

/* Dismissible entry point to the AI onboarding interview, shown until the
   user has a completed session (spec: ai-onboarding, dashboard entry point). */
export function OnboardingNudge() {
  const router = useRouter();
  // Lazy init instead of an effect: rendering is gated on statusQuery.data,
  // which only resolves client-side, so SSR/hydration both render null.
  const [dismissed, setDismissed] = React.useState(
    () =>
      typeof localStorage !== "undefined" &&
      localStorage.getItem(ONBOARDING_DISMISSED_KEY) === "1",
  );
  const statusQuery = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: fetchOnboardingStatus,
  });

  if (dismissed || !statusQuery.data || statusQuery.data.has_completed) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
      <CoachCapsule
        message={
          statusQuery.data.has_active
            ? "Your setup interview is waiting — pick up where you left off"
            : "Finish setting up — a 2-minute chat builds your budget"
        }
        cta={statusQuery.data.has_active ? "Resume" : "Start"}
        accent="violet"
        onClick={() => router.push("/onboarding")}
        style={{ flex: 1 }}
      />
      <button
        aria-label="Dismiss"
        onClick={() => {
          globalThis.localStorage.setItem(ONBOARDING_DISMISSED_KEY, "1");
          setDismissed(true);
        }}
        style={{
          border: "none",
          background: "transparent",
          cursor: "pointer",
          color: "var(--text-subtle)",
          padding: 6,
        }}
      >
        <Icon name="x" size={16} />
      </button>
    </div>
  );
}
