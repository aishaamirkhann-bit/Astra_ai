import PageShell from "@/components/PageShell";
import SellerInventoryForm from "@/components/seller/SellerInventoryForm";
import SellerEscrowOrders from "@/components/seller/SellerEscrowOrders";
export const metadata={title:"Seller Dashboard | ASTRA AI"};
export default function SellerDashboard(){return <PageShell active="Seller Dashboard" title="Seller Management" subtitle="Manage verified inventory and monitor buyer escrow orders in real time."><SellerInventoryForm/><SellerEscrowOrders/></PageShell>}
