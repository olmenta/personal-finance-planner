import { CoverPromptProvider } from "@/components/budget/CoverPrompt";
import { CurrentUserProvider, type CurrentUser } from "@/components/shell/CurrentUser";
import { auth0 } from "@/lib/auth0";
import { SelectedMonthProvider } from "@/lib/selectedMonth";
import { BottomNav } from "@/components/shell/BottomNav";
import { Sidebar } from "@/components/shell/Sidebar";

async function signedInUser(): Promise<CurrentUser | null> {
  if (!auth0) return null; // auth disabled: the development user
  const session = await auth0.getSession();
  if (!session) return null;
  const { name, email, picture } = session.user as { name?: string; email?: string; picture?: string };
  return { name: name || email || "You", email: email ?? null, picture: picture ?? null, canLogOut: true };
}

export default async function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const user = await signedInUser();
  return (
    <CurrentUserProvider user={user}>
    <SelectedMonthProvider>
    <CoverPromptProvider>
      <div className="app-shell">
        <Sidebar />
        <div className="app-main-col">
          <main className="app-main">{children}</main>
          <BottomNav />
        </div>
      </div>
    </CoverPromptProvider>
    </SelectedMonthProvider>
    </CurrentUserProvider>
  );
}
