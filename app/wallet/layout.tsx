import AuthenticatedRoute from "@/components/AuthenticatedRoute";

export default function WalletLayout({ children }: { children: React.ReactNode }) {
  return <AuthenticatedRoute>{children}</AuthenticatedRoute>;
}
