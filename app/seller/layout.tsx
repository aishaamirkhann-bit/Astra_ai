import SellerRouteGuard from "@/components/seller/SellerRouteGuard";

export default function SellerLayout({ children }: { children: React.ReactNode }) {
  return <SellerRouteGuard>{children}</SellerRouteGuard>;
}
