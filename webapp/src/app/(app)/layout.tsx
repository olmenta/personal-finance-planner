import { CoverPromptProvider } from "@/components/budget/CoverPrompt";
import { SelectedMonthProvider } from "@/lib/selectedMonth";
import { BottomNav } from "@/components/shell/BottomNav";
import { CoachRail } from "@/components/shell/CoachRail";
import { Sidebar } from "@/components/shell/Sidebar";

export default function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <SelectedMonthProvider>
    <CoverPromptProvider>
      <div className="app-shell">
        <Sidebar />
        <div className="app-main-col">
          <main className="app-main">{children}</main>
          <BottomNav />
        </div>
        <CoachRail />
      </div>
    </CoverPromptProvider>
    </SelectedMonthProvider>
  );
}
