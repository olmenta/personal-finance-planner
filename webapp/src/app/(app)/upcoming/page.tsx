import { redirect } from "next/navigation";

/* Upcoming payments became Future (spec: navigation); keep old links working. */
export default async function UpcomingRedirect({
  searchParams,
}: Readonly<{ searchParams: Promise<{ month?: string }> }>) {
  const { month } = await searchParams;
  redirect(month ? `/future?month=${encodeURIComponent(month)}` : "/future");
}
