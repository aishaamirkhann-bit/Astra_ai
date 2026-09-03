import { notFound } from "next/navigation";
import PageShell from "@/components/PageShell";
import CategoryProductsClient from "@/components/categories/CategoryProductsClient";
import { getCategories } from "@/lib/api";

export const dynamicParams = true;

export default async function CategoryPage({ params }: { params: { slug: string } }) {
  const categories = await getCategories().catch(() => []);
  const category = categories.find((item) => item.slug === params.slug);
  if (!category) return notFound();

  return (
    <PageShell active="Categories" title={category.name} subtitle={`Browse ${category.name} from the database catalog.`}>
      <CategoryProductsClient categoryName={category.name} />
    </PageShell>
  );
}