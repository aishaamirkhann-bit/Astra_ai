import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import HomeClient from "@/components/HomeClient";
import { getHomePage } from "@/lib/api";

export default async function HomePage() {
  const cookieStore = cookies();
  if (process.env.NODE_ENV === "production" && !cookieStore.has("astra_token")) redirect("/login");
  const cookieHeader = cookieStore.getAll().map(({ name, value }) => `${name}=${value}`).join("; ");
  let data;
  try {
    data = await getHomePage(cookieHeader);
  } catch {
    redirect("/login");
  }
  return <HomeClient data={data} />;
}
