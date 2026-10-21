import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import HomeClient from "@/components/HomeClient";
import { getHomePage } from "@/lib/api";

export default async function BuyerDashboardPage() {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map(({ name, value }) => `${name}=${value}`)
    .join("; ");

  let data;
  try {
    data = await getHomePage(cookieHeader);
  } catch {
    redirect("/login?next=%2Fbuyer%2Fdashboard");
  }

  if (data.user.role !== "buyer") redirect("/seller/dashboard");
  return <HomeClient data={data} />;
}
