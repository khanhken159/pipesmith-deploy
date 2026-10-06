"use client";

import {
  BOX,
  edgePath,
  isGrouped,
  joinPath,
  joinTouches,
  layoutCatalog,
  lineageClosure,
  tableOf,
  truncate,
  type DiagramLayout,
  type PlacedTable,
} from "@/lib/diagram";
import { formatNumber, LAYER_LABELS } from "@/lib/format";
import type { CatalogView, JoinInfo } from "@/lib/types";

const LAYER_COLORS = {
  source: "var(--layer-source)",
  staging: "var(--layer-staging)",
  mart: "var(--layer-mart)",
};

interface DiagramProps {
  catalog: CatalogView;
  selected: string;
  onSelect: (id: string) => void;
}

function TableNode({
  node,
  selected,
  dim,
  onSelect,
}: {
  node: PlacedTable;
  selected: boolean;
  dim: boolean;
  onSelect: (id: string) => void;
}) {
  const { table } = node;
  const parts = [`${table.columns.length} cột`, table.rows !== null ? `${formatNumber(table.rows)} dòng` : ""];
  const duplicates = table.duplicate_keys ?? 0;
  return (
    <g
      className={`node${selected ? " selected" : ""}${dim ? " dim" : ""}`}
      transform={`translate(${node.x} ${node.y})`}
      tabIndex={0}
      role="button"
      aria-pressed={selected}
      aria-label={`${LAYER_LABELS[table.layer]} ${table.name}, ${parts.filter(Boolean).join(", ")}`}
      onClick={() => onSelect(table.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(table.id);
        }
      }}
    >
      <title>{table.id}</title>
      <rect className="box" width={BOX.width} height={BOX.height} rx={8} />
      <rect className="bar" width={5} height={BOX.height} rx={2} fill={LAYER_COLORS[table.layer]} />
      <text x={16} y={23} fontWeight={600}>
        {truncate(table.name, 23)}
      </text>
      <text className="sub" x={16} y={43}>
        {parts.filter(Boolean).join(" · ")}
        {duplicates > 0 && <tspan fill="var(--warn)"> · ⚠ {formatNumber(duplicates)} khóa trùng</tspan>}
      </text>
    </g>
  );
}

function JoinEdges({ joins, layout }: { joins: JoinInfo[]; layout: DiagramLayout }) {
  return joins.map((join) => {
    const from = tableOf(join.left, layout.nodes);
    const to = tableOf(join.right, layout.nodes);
    if (!from || !to) return null;
    const midX = (Math.min(from.x, to.x) + Math.max(from.x, to.x) + BOX.width) / 2;
    const midY = (from.y + to.y + BOX.height) / 2;
    return (
      <g key={`${join.left}->${join.right}`}>
        <path className="edge join" d={joinPath(from, to)} />
        {join.match_pct != null && (
          <text className="edge-label" x={from.x === to.x ? from.x + BOX.width + 24 : midX} y={midY}>
            {Math.round(join.match_pct)}%
          </text>
        )}
      </g>
    );
  });
}

function related(catalog: CatalogView, selected: string): Set<string> | null {
  if (!selected) return null;
  if (!isGrouped(catalog)) return lineageClosure(selected, catalog.lineage);
  const table = catalog.tables.find((t) => t.id === selected);
  const partners = catalog.joins.filter((j) => table && joinTouches(j, table));
  const ids = partners.flatMap((j) => [j.left, j.right].map((label) => label.split(".").slice(0, -1).join(".")));
  return new Set([selected, ...ids]);
}

export function CatalogDiagram({ catalog, selected, onSelect }: DiagramProps) {
  const layout = layoutCatalog(catalog);
  const hot = related(catalog, selected);
  const table = catalog.tables.find((t) => t.id === selected);
  const joins = isGrouped(catalog) && table ? catalog.joins.filter((j) => joinTouches(j, table)) : [];
  return (
    <div className="diagram-scroll">
      <svg
        className="diagram"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        width={layout.width}
        height={layout.height}
        role="group"
        aria-label="Sơ đồ bảng và quan hệ"
      >
        {layout.labels.map((label) => (
          <text key={`${label.text}-${label.x}-${label.y}`} className="layer-title" x={label.x} y={label.y}>
            {label.text}
          </text>
        ))}
        {catalog.lineage.map((edge) => {
          const from = layout.nodes[edge.source];
          const to = layout.nodes[edge.target];
          if (!from || !to) return null;
          const lit = hot?.has(edge.source) && hot.has(edge.target);
          return (
            <path key={`${edge.source}->${edge.target}`} className={lit ? "edge hot" : "edge"} d={edgePath(from, to)} />
          );
        })}
        {Object.values(layout.nodes).map((node) => (
          <TableNode
            key={node.table.id}
            node={node}
            selected={node.table.id === selected}
            dim={Boolean(hot && !hot.has(node.table.id))}
            onSelect={onSelect}
          />
        ))}
        <JoinEdges joins={joins} layout={layout} />
      </svg>
    </div>
  );
}
