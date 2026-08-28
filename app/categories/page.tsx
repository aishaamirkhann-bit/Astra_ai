import PageShell from "@/components/PageShell";
import CategoriesClient from "@/components/categories/CategoriesClient";

export default function CategoriesPage() {
  return (
    <PageShell
      active="Categories"
      title="Categories"
      subtitle="Browse the full catalog — from electronics to fashion, jewelry, and beauty."
    >
      <CategoriesClient />
    </PageShell>
  );
}
