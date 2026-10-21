import PageShell from "@/components/PageShell";
import VendorPricing from "@/components/b2b/VendorPricing";

export const metadata = { title: "Vendor Plans | ASTRA AI" };

export default function VendorPricingPage() {
  return <PageShell active="Seller Dashboard" title="Vendor Subscriptions" subtitle="SaaS plans for wholesalers and distributors, billed monthly in PKR.">
    <VendorPricing />
  </PageShell>;
}
