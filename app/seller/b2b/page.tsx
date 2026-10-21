import PageShell from "@/components/PageShell";
import DistributionLedgerPanel from "@/components/b2b/DistributionLedgerPanel";
import VendorBidDesk from "@/components/b2b/VendorBidDesk";

export const metadata = { title: "B2B Supplier Desk | ASTRA AI" };

export default function SellerB2BPage() {
  return <PageShell active="Seller Dashboard" title="B2B Supplier Desk" subtitle="Submit wholesale quotes, track commission estimates, and manage retailer credit and replenishment signals.">
    <VendorBidDesk />
    <DistributionLedgerPanel />
  </PageShell>;
}
