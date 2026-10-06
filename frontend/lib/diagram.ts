// Bố cục sơ đồ dữ liệu.
// - Lần chạy (có lineage): mỗi tầng raw → staging → mart một cột; thứ tự theo trung bình vị trí bảng cha (ít cạnh cắt).
// - Kho nguồn (chưa có lineage, bảng có nhóm hệ thống): xếp các nhóm vào 3 cột; cạnh khóa nối vẽ khi chọn một bảng.

import { LAYER_LABELS } from "./format";
import type { CatalogView, JoinInfo, Layer, LineageEdge, TableInfo } from "./types";

export const BOX = { width: 204, height: 58, gapY: 16, colGap: 76, pad: 16, head: 30 };
const LAYER_ORDER: Layer[] = ["source", "staging", "mart"];

export interface PlacedTable {
  table: TableInfo;
  x: number;
  y: number;
}

export interface DiagramLabel {
  text: string;
  x: number;
  y: number;
}

export interface DiagramLayout {
  nodes: Record<string, PlacedTable>;
  labels: DiagramLabel[];
  width: number;
  height: number;
}

const GROUP_COLUMNS = 3;
const GROUP_GAP = 44;

function parentsOf(id: string, lineage: LineageEdge[]): string[] {
  return lineage.filter((edge) => edge.target === id).map((edge) => edge.source);
}

function orderLayer(tables: TableInfo[], lineage: LineageEdge[], rank: Record<string, number>): TableInfo[] {
  const score = (table: TableInfo): number => {
    const ranks = parentsOf(table.id, lineage)
      .map((id) => rank[id])
      .filter((r) => r !== undefined);
    return ranks.length ? ranks.reduce((a, b) => a + b, 0) / ranks.length : Number.MAX_SAFE_INTEGER;
  };
  return [...tables].sort((a, b) => score(a) - score(b) || a.name.localeCompare(b.name));
}

function layoutLayers(catalog: CatalogView): DiagramLayout {
  const nodes: Record<string, PlacedTable> = {};
  const labels: DiagramLabel[] = [];
  const rank: Record<string, number> = {};
  let tallest = 0;
  for (const layer of LAYER_ORDER) {
    const tables = catalog.tables.filter((t) => t.layer === layer);
    if (tables.length === 0) continue;
    const x = BOX.pad + labels.length * (BOX.width + BOX.colGap);
    labels.push({ text: LAYER_LABELS[layer], x, y: BOX.pad + 14 });
    orderLayer(tables, catalog.lineage, rank).forEach((table, index) => {
      rank[table.id] = index;
      nodes[table.id] = { table, x, y: BOX.pad + BOX.head + index * (BOX.height + BOX.gapY) };
    });
    tallest = Math.max(tallest, tables.length);
  }
  const width = BOX.pad * 2 + Math.max(labels.length, 1) * BOX.width + Math.max(labels.length - 1, 0) * BOX.colGap;
  const height = BOX.pad * 2 + BOX.head + tallest * (BOX.height + BOX.gapY) - BOX.gapY;
  return { nodes, labels, width, height };
}

function groupsOf(tables: TableInfo[]): [string, TableInfo[]][] {
  const groups = new Map<string, TableInfo[]>();
  for (const table of tables) {
    const key = table.group || "Khác";
    groups.set(key, [...(groups.get(key) ?? []), table]);
  }
  return [...groups.entries()];
}

function layoutGroups(tables: TableInfo[]): DiagramLayout {
  const nodes: Record<string, PlacedTable> = {};
  const labels: DiagramLabel[] = [];
  const bottoms = Array<number>(GROUP_COLUMNS).fill(BOX.pad);
  for (const [title, members] of groupsOf(tables)) {
    const column = bottoms.indexOf(Math.min(...bottoms));
    const x = BOX.pad + column * (BOX.width + GROUP_GAP);
    labels.push({ text: title, x, y: bottoms[column] + 14 });
    const top = bottoms[column] + BOX.head;
    members.forEach((table, index) => {
      nodes[table.id] = { table, x, y: top + index * (BOX.height + BOX.gapY) };
    });
    bottoms[column] = top + members.length * (BOX.height + BOX.gapY) + 8;
  }
  const loop = 40; // chỗ cho đường nối hai bảng cùng cột vòng ra bên phải
  const width = BOX.pad * 2 + GROUP_COLUMNS * BOX.width + (GROUP_COLUMNS - 1) * GROUP_GAP + loop;
  return { nodes, labels, width, height: Math.max(...bottoms) + BOX.pad };
}

/** Kho nguồn chưa chạy pipeline: không có lineage, bảng đã được nhóm theo hệ thống. */
export function isGrouped(catalog: CatalogView): boolean {
  return catalog.lineage.length === 0 && catalog.tables.some((t) => t.group);
}

export function layoutCatalog(catalog: CatalogView): DiagramLayout {
  return isGrouped(catalog) ? layoutGroups(catalog.tables) : layoutLayers(catalog);
}

export function edgePath(from: PlacedTable, to: PlacedTable): string {
  const x1 = from.x + BOX.width;
  const y1 = from.y + BOX.height / 2;
  const x2 = to.x;
  const y2 = to.y + BOX.height / 2;
  const bend = Math.max((x2 - x1) / 2, 40);
  return `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`;
}

/** Đường nối hai bảng bất kỳ (khóa nối): đi từ cạnh gần nhau nhất; cùng cột thì vòng ra bên phải. */
export function joinPath(a: PlacedTable, b: PlacedTable): string {
  const ya = a.y + BOX.height / 2;
  const yb = b.y + BOX.height / 2;
  if (a.x === b.x) {
    const x = a.x + BOX.width;
    return `M ${x} ${ya} C ${x + 36} ${ya}, ${x + 36} ${yb}, ${x} ${yb}`;
  }
  const [left, right, yl, yr] = a.x < b.x ? [a, b, ya, yb] : [b, a, yb, ya];
  const x1 = left.x + BOX.width;
  const x2 = right.x;
  const bend = Math.max((x2 - x1) / 2, 30);
  return `M ${x1} ${yl} C ${x1 + bend} ${yl}, ${x2 - bend} ${yr}, ${x2} ${yr}`;
}

/** Bảng đã chọn + toàn bộ bảng phía trên (nguồn của nó) và phía dưới (nơi dùng nó). */
export function lineageClosure(id: string, lineage: LineageEdge[]): Set<string> {
  const related = new Set([id]);
  const walk = (start: string, forward: boolean) => {
    const queue = [start];
    while (queue.length) {
      const current = queue.shift() as string;
      for (const edge of lineage) {
        const [from, to] = forward ? [edge.source, edge.target] : [edge.target, edge.source];
        if (from === current && !related.has(to)) {
          related.add(to);
          queue.push(to);
        }
      }
    }
  };
  walk(id, true);
  walk(id, false);
  return related;
}

/** Phần bảng của nhãn cột `bang.cot` hoặc `schema.bang.cot`. */
export function ownerOf(columnLabel: string): string {
  return columnLabel.split(".").slice(0, -1).join(".");
}

export function tableOf(columnLabel: string, nodes: Record<string, PlacedTable>): PlacedTable | undefined {
  const owner = ownerOf(columnLabel);
  return nodes[owner] ?? Object.values(nodes).find((n) => n.table.name === owner);
}

export function joinTouches(join: JoinInfo, table: TableInfo): boolean {
  return [ownerOf(join.left), ownerOf(join.right)].some((owner) => owner === table.id || owner === table.name);
}

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}
