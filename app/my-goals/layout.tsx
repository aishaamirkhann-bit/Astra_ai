import AuthenticatedRoute from "@/components/AuthenticatedRoute";

export default function MyGoalsLayout({ children }: { children: React.ReactNode }) {
  return <AuthenticatedRoute>{children}</AuthenticatedRoute>;
}
