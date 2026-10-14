import PageShell from "@/components/PageShell";
import SellerDashboardHome from "@/components/seller/SellerDashboardHome";

export const metadata = { title: "Seller Dashboard | ASTRA AI" };

export default function SellerDashboard() {
  return (
    <PageShell
      active="Seller Dashboard"
      title="Seller Dashboard"
      subtitle="Your business overview, performance, and daily seller tools."
    >
      <SellerDashboardHome />
    </PageShell>
  );
}
