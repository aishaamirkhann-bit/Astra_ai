import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/api";

export default async function AuthenticatedRoute({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.getAll().map(({ name, value }) => `${name}=${value}`).join("; ");
  try {
    await getCurrentUser(cookieHeader);
  } catch {
    redirect("/login");
  }
  return <>{children}</>;
}
