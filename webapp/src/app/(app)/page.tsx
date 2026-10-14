"use client";

import { useQuery } from "@tanstack/react-query";
import { AddTransactionDialog } from "@/components/AddTransactionDialog";
import {
  CoachLine,
  FutureWidget,
  HomeHeaderLine,
  MonthWidget,
  NoAccounts,
  PriorityAction,
  RecommendationGroups,
} from "@/components/home/HomeWidgets";
import { OnboardingNudge } from "@/components/home/OnboardingNudge";
import { TopBar } from "@/components/shell/TopBar";
import { Button } from "@/components/ui/Button";
import { ErrorPanel, SkeletonPanel } from "@/components/ui/QueryStates";
import { fetchHome } from "@/lib/api";

/* Home (spec: home): what to resolve now. One server snapshot per visit
   (GET /home): month status, the exact breakdown, one priority action,
   grouped suggestions and the Future status. Categories live in Budget,
   activity in Transactions, commitments in Future. */
export default function HomePage() {
  const home = useQuery({ queryKey: ["home"], queryFn: fetchHome });

  return (
    <>
      <TopBar title="Home" sub="What to resolve now" />
      <div className="app-content" style={{ maxWidth: 760 }}>
        <OnboardingNudge />
        {home.isError ? (
          <ErrorPanel message="We couldn't load your month." onRetry={() => home.refetch()} />
        ) : !home.data ? (
          <>
            <SkeletonPanel rows={1} rowHeight={40} />
            <SkeletonPanel rows={5} rowHeight={36} />
          </>
        ) : home.data.status === "no_accounts" ? (
          <NoAccounts />
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
              <HomeHeaderLine home={home.data} />
              <AddTransactionDialog>
                <Button variant="secondary" size="sm" iconLeft="plus">Add transaction</Button>
              </AddTransactionDialog>
            </div>
            <CoachLine home={home.data} />
            <MonthWidget home={home.data} />
            <PriorityAction home={home.data} />
            <RecommendationGroups home={home.data} />
            <FutureWidget home={home.data} />
          </>
        )}
      </div>
    </>
  );
}
