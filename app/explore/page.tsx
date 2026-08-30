import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import PageShell from "@/components/PageShell";
import ExploreClient from "@/components/explore/ExploreClient";
import { getExploreData } from "@/lib/api";

export default async function ExplorePage({
  searchParams,
}: {
  searchParams: { q?: string; category?: string };
}) {
  const cookieHeader = cookies().getAll().map(({ name, value }) => `${name}=${value}`).join("; ");
  let exploreData;
  try {
    exploreData = await getExploreData(cookieHeader);
  } catch {
    redirect("/login");
  }
  return (
    <PageShell
      active="Explore"
      title="Explore"
      subtitle="Search by text, voice, or image — ASTRA blends keyword and semantic matching."
    >
      <ExploreClient
        initialQuery={searchParams.q?.replace(/\+/g, " ") ?? ""}
        initialCategory={searchParams.category ?? null}
        initialWalletBalance={exploreData.available_balance}
      />
    </PageShell>
  );
}
