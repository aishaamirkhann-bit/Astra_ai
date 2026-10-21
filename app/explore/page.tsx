import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import PageShell from "@/components/PageShell";
import ExploreClient from "@/components/explore/ExploreClient";
import { getExploreData } from "@/lib/api";

export default async function ExplorePage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; category?: string }>;
}) {
  const [query, cookieStore] = await Promise.all([searchParams, cookies()]);
  const cookieHeader = cookieStore.getAll().map(({ name, value }) => `${name}=${value}`).join("; ");
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
        initialQuery={query.q?.replace(/\+/g, " ") ?? ""}
        initialCategory={query.category ?? null}
        initialWalletBalance={exploreData.available_balance}
      />
    </PageShell>
  );
}
