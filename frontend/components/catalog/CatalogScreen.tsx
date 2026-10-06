"use client";

import { useState } from "react";

import { isGrouped, ownerOf } from "@/lib/diagram";
import type { CatalogView, JoinInfo } from "@/lib/types";
import { usePoll } from "@/lib/usePoll";

import { Card, Empty, ErrorBox, Loading } from "../ui";
import { CatalogDiagram } from "./CatalogDiagram";
import { SchemaPanel } from "./SchemaPanel";

function JoinsTable({ joins }: { joins: JoinInfo[] }) {
  return (
    <Card title="Quan hệ giữa các bảng (khóa nối)">
      {joins.length === 0 && <Empty>Không tìm thấy JOIN nào (ví dụ pipeline chỉ UNION các nguồn).</Empty>}
      {joins.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Cột bên trái</th>
                <th>Cột bên phải</th>
                <th>Kiểu</th>
                <th className="num" title="% dòng bên trái tìm thấy giá trị ở bên phải (đo trên dữ liệu thật)">
                  Khớp
                </th>
                <th>Trong model</th>
              </tr>
            </thead>
            <tbody>
              {joins.map((join) => (
                <tr key={`${join.left}-${join.right}-${join.model}`}>
                  <td className="mono">{join.left}</td>
                  <td className="mono">{join.right}</td>
                  <td>
                    <span className={join.how === "gợi ý" ? "badge warn" : "badge info"}>{join.how}</span>
                  </td>
                  <td className="num">
                    <MatchBadge pct={join.match_pct} />
                  </td>
                  <td className="mono muted">{join.model || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function MatchBadge({ pct }: { pct?: number | null }) {
  if (pct == null) return <span className="muted">—</span>;
  const tone = pct >= 99 ? "ok" : pct >= 90 ? "warn" : "danger";
  return <span className={`badge ${tone}`}>{pct.toLocaleString("vi-VN")}%</span>;
}

function Legend({ grouped }: { grouped: boolean }) {
  if (grouped) {
    return (
      <div className="legend">
        <span>Bảng xếp theo hệ thống nguồn · bấm một bảng để thấy khóa nối (nét đứt, % dòng khớp)</span>
      </div>
    );
  }
  return <LayerLegend />;
}

function LayerLegend() {
  return (
    <div className="legend">
      <span>
        <i style={{ background: "var(--layer-source)" }} />
        Nguồn (raw)
      </span>
      <span>
        <i style={{ background: "var(--layer-staging)" }} />
        Staging (làm sạch)
      </span>
      <span>
        <i style={{ background: "var(--layer-mart)" }} />
        Mart (bảng đích)
      </span>
      <span>Đường nối = lineage (bảng trái được bảng phải đọc)</span>
    </div>
  );
}

function defaultTable(catalog: CatalogView): string {
  const mart = catalog.tables.find((t) => t.layer === "mart");
  if (mart) return mart.id;
  const degree = (id: string) => catalog.joins.filter((j) => [j.left, j.right].some((c) => ownerOf(c) === id)).length;
  const best = [...catalog.tables].sort((a, b) => degree(b.id) - degree(a.id))[0];
  return best && degree(best.id) > 0 ? best.id : "";
}

export function CatalogScreen({ path, emptyText }: { path: string; emptyText: string }) {
  const { data, error, loading, refresh } = usePoll<CatalogView>(path, null);
  const [picked, setPicked] = useState<string | null>(null);
  if (loading && !data) return <Loading text="Đang đọc cấu trúc dữ liệu (DuckDB + sqlglot)…" />;
  if (!data) return <ErrorBox message={error || "Không tải được cấu trúc dữ liệu."} onRetry={refresh} />;
  if (data.tables.length === 0) return <Empty>{emptyText}</Empty>;
  // Mặc định chọn sẵn bảng đích (mart), hoặc bảng nguồn có nhiều quan hệ nhất; bấm lại bảng đang chọn để bỏ chọn.
  const selected = picked ?? defaultTable(data);
  const toggle = (id: string) => setPicked(id === selected ? "" : id);
  return (
    <>
      <div className="catalog-layout">
        <Card title={`Sơ đồ (${data.tables.length} bảng)`} actions={<Legend grouped={isGrouped(data)} />}>
          <CatalogDiagram catalog={data} selected={selected} onSelect={toggle} />
        </Card>
        <SchemaPanel catalog={data} table={data.tables.find((t) => t.id === selected)} onSelect={setPicked} />
      </div>
      <JoinsTable joins={data.joins} />
    </>
  );
}
