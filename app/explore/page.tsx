import PageShell from "@/components/PageShell";
import ExploreClient from "@/components/explore/ExploreClient";

export default function ExplorePage({
  searchParams,
}: {
  searchParams: { q?: string; category?: string };
}) {
  return (
    <PageShell
      active="Explore"
      title="Explore"
      subtitle="Search by text, voice, or image — ASTRA blends keyword and semantic matching."
    >
      <ExploreClient
        initialQuery={searchParams.q?.replace(/\+/g, " ") ?? ""}
        initialCategory={searchParams.category ?? null}
      />
    </PageShell>
  );
}
