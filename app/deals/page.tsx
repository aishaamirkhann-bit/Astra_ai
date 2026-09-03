import PageShell from "@/components/PageShell";
import DealsClient from "@/components/deals/DealsClient";
import { getDeals } from "@/lib/api";

export default async function DealsPage() {
  const deals = await getDeals();

  return (
    <PageShell
      active="Deals"
      title="Deals & AI Steals"
      subtitle="Astra's AI Trust Agent continuously verifies below-market prices, vendor fulfillment, product authenticity, and price stability before a listing appears here."
    >
      <DealsClient initialDeals={deals} />
    </PageShell>
  );
}
