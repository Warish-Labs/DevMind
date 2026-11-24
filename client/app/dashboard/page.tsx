import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";

/**
 * /dashboard — Smart redirect.
 * - Signed-in users are sent to the projects list (app shell).
 * - Unauthenticated users are redirected to sign-in.
 */
export default async function DashboardPage() {
  const { userId } = await auth();
  if (!userId) {
    redirect("/sign-in?redirect_url=/dashboard");
  }
  redirect("/projects");
}
