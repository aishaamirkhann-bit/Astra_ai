import AuthenticatedRoute from "@/components/AuthenticatedRoute";

export default function OrdersLayout({ children }: { children: React.ReactNode }) {
  return <AuthenticatedRoute>{children}</AuthenticatedRoute>;
}
