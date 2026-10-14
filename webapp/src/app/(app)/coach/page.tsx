import { redirect } from "next/navigation";

/* The coach lives on Home now (spec: navigation). */
export default function CoachPage() {
  redirect("/");
}
