"use client";

import { joinTouches } from "@/lib/diagram";
import { formatNumber, LAYER_LABELS } from "@/lib/format";
import type { CatalogView, ColumnInfo, TableInfo } from "@/lib/types";

import { Card, Empty } from "../ui";

function NullBar({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="muted">—</span>;
  return (
    <span className="null-bar">
      {pct.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%
      <span className="track" aria-hidden>
        <span className="fill" style={{ width: `${Math.min(pct, 100)}%` }} />
      </span>
    </span>
  );
}

function ColumnsTable({ columns }: { columns: ColumnInfo[] }) {
  return (
    <div className="table-wrap" style={{ maxHeight: 360 }}>
      <table>
        <thead>
          <tr>
            <th>Cột</th>
            <th>Kiểu</th>
            <th className="num">% rỗng</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((column) => (
            <tr key={column.name}>
              <td className="mono">
                {column.name} {column.is_key && <span className="badge info">khóa</span>}
              </td>
              <td className="mono muted">{column.type || "—"}</td>
              <td className="num">
                <NullBar pct={column.null_pct} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Neighbours({ label, ids, onSelect }: { label: string; ids: string[]; onSelect: (id: string) => void }) {
  return (
    <div className="row small">
      <span className="muted">{label}:</span>
      {ids.length === 0 && <span className="muted">—</span>}
      {ids.map((id) => (
        <button key={id} type="button" className="chip mono" onClick={() => onSelect(id)}>
          {id}
        </button>
      ))}
    </div>
  );
}

export function SchemaPanel({
  catalog,
  table,
  onSelect,
}: {
  catalog: CatalogView;
  table: TableInfo | undefined;
  onSelect: (id: string) => void;
}) {
  if (!table) {
    return (
      <Card title="Schema">
        <Empty>Bấm vào một bảng trên sơ đồ để xem cột, kiểu, % rỗng, khóa và quan hệ.</Empty>
      </Card>
    );
  }
  const upstream = catalog.lineage.filter((e) => e.target === table.id).map((e) => e.source);
  const downstream = catalog.lineage.filter((e) => e.source === table.id).map((e) => e.target);
  const joins = catalog.joins.filter((join) => joinTouches(join, table));
  return (
    <Card
      title={<span className="mono">{table.name}</span>}
      actions={<span className="badge muted">{LAYER_LABELS[table.layer]}</span>}
    >
      <div className="stack" style={{ gap: 10 }}>
        {table.description && <p className="small">{table.description}</p>}
        <div className="row small muted">
          {table.group && <span className="badge info">{table.group}</span>}
          <span>{table.columns.length} cột</span>
          <span>·</span>
          <span>{formatNumber(table.rows)} dòng</span>
          {table.file && <span className="mono">· {table.file}</span>}
        </div>
        {(table.duplicate_keys ?? 0) > 0 && (
          <div className="alert warn">
            <span>
              {formatNumber(table.duplicate_keys)} dòng trùng khóa — pipeline cần bỏ trùng hoặc làm rõ với nghiệp vụ.
            </span>
          </div>
        )}
        {catalog.lineage.length > 0 && (
          <>
            <Neighbours label="Đọc từ" ids={upstream} onSelect={onSelect} />
            <Neighbours label="Được dùng bởi" ids={downstream} onSelect={onSelect} />
          </>
        )}
        <ColumnsTable columns={table.columns} />
        {joins.length > 0 && (
          <div>
            <h3>Khóa nối liên quan</h3>
            <ul className="plain mono small">
              {joins.map((join) => (
                <li key={`${join.left}-${join.right}-${join.model}`}>
                  {join.left} = {join.right}{" "}
                  <span className="muted">
                    ({join.how}
                    {join.match_pct != null && `, khớp ${join.match_pct}% dòng`})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}
