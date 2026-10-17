import PageShell from "@/components/PageShell";
import ActiveOrdersList from "@/components/orders/ActiveOrdersList";
import AuditLogView from "@/components/orders/AuditLogView";

export default function OrdersPage() {
  return (
    <PageShell
      active="Orders"
      title="Orders & Reversible Checkout"
      subtitle="Every order carries a 1-minute grace window and an immutable consent record."
    >
      <ActiveOrdersList />
      <AuditLogView />
    </PageShell>
  );
}
