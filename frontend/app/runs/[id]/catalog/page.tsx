import { CatalogScreen } from "@/components/catalog/CatalogScreen";

export default async function RunCatalogPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CatalogScreen path={`/runs/${id}/catalog`} emptyText="Lần chạy chưa có bảng nào để hiển thị." />;
}
