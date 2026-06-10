"use client";

import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/* Server-state defaults (design D6): money data wants freshness, so refetch
   on focus stays on; one retry keeps backend-down failures fast. */

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
