// Khuôn dữ liệu trả về từ API FastAPI (khớp src/api/requests.py, src/models/*, src/services/catalog.py).

export type RunStatus =
  | "running"
  | "waiting_clarification"
  | "waiting_plan_review"
  | "waiting_rescue"
  | "waiting_review"
  | "approved"
  | "failed";

export interface RunSummary {
  target?: string | null;
  mode?: string | null;
  fix_attempts?: number;
  rescue_count?: number;
  review_rounds?: number;
  optimization?: string | null;
  improvement_pct?: number | null;
  llm_calls?: number;
  tokens?: number;
  cost_usd?: number;
  simulated?: boolean;
  workspace?: string | null;
  error?: string;
}

export interface RunRecord {
  id: string;
  request_text: string;
  requester: string;
  status: RunStatus;
  provider: string;
  model: string;
  created_at: string;
  updated_at: string;
  summary: RunSummary;
}

export interface StepEvent {
  node: string;
  label: string;
  ok: boolean;
  detail: string;
  seconds: number;
  tokens: number;
}

export interface ClarifyQuestion {
  id: string;
  question: string;
  options: string[];
}

export interface PlanStep {
  title: string;
  detail: string;
  reason: string;
}

export interface PlanPending {
  kind: "plan";
  summary: string;
  steps: PlanStep[];
  spec: Spec;
  sources: string[];
  next_steps: string;
}

export type Pending =
  | { kind: "clarify"; unknowns: string[]; questions: ClarifyQuestion[] }
  | PlanPending
  | { kind: "rescue"; error: string; fix_attempts: number }
  | { kind: "review"; run_id: string; requester: string };

export interface OutputColumn {
  name: string;
  type: string;
  description?: string;
  references?: string;
}

export interface Spec {
  target?: string;
  mode?: string;
  mode_reason?: string;
  grain?: string[];
  output_columns?: OutputColumn[];
  metrics?: { name: string; description: string }[];
  filters?: string[];
  assumptions?: string[];
  plan_summary?: string;
  plan?: PlanStep[];
}

export interface MeasuredItem {
  node: string;
  check: string;
  result: string;
  passed: boolean | null;
}

export interface Evidence {
  measured?: MeasuredItem[];
  claimed?: string[];
}

export interface QueryMetrics {
  median_ms: number;
  runs: number;
  peak_memory_mb?: number | null;
}

export interface Optimization {
  original_sql?: string;
  proposed_sql?: string;
  findings?: { rule: string; message: string }[];
  before?: QueryMetrics | null;
  after?: QueryMetrics | null;
  improvement_pct?: number | null;
  decision?: "applied" | "skipped";
  reason?: string;
  attempts?: number;
  equivalence?: { dataset: string; equal: boolean; detail: string }[];
  llm_cost_usd?: number;
  explanation?: string;
  warehouse_hints?: string[];
}

export interface Sandbox {
  passed?: boolean;
  error?: string;
  target_rows?: number;
  sample?: Record<string, string>[];
  models_ok?: number;
  models_total?: number;
  tests_ok?: number;
  tests_total?: number;
}

export interface AnsweredQuestion {
  id: string;
  question: string;
  answer: string;
}

export interface RunDetail {
  record: RunRecord;
  busy: boolean;
  pending: Pending | null;
  events: StepEvent[];
  spec: Spec;
  answered: AnsweredQuestion[];
  evidence: Evidence;
  optimization: Optimization;
  sandbox: Sandbox;
  code_notes: string[];
  test_notes: string[];
}

export interface RunFiles {
  code_files: Record<string, string>;
  test_files: Record<string, string>;
  previous_files: Record<string, string>;
}

export type Layer = "source" | "staging" | "mart";

export interface ColumnInfo {
  name: string;
  type: string;
  null_pct: number | null;
  is_key: boolean;
}

export interface TableInfo {
  id: string;
  name: string;
  layer: Layer;
  columns: ColumnInfo[];
  rows: number | null;
  duplicate_keys: number | null;
  file: string;
  group?: string;
  description?: string;
}

export interface JoinInfo {
  left: string;
  right: string;
  how: string;
  model: string;
  match_pct?: number | null;
}

export interface LineageEdge {
  source: string;
  target: string;
}

export interface CatalogView {
  tables: TableInfo[];
  lineage: LineageEdge[];
  joins: JoinInfo[];
}

export interface AgentStatus {
  status: string;
  agent: string;
  llm_provider: string;
  models: string;
  simulated: boolean;
  require_separate_reviewer: boolean;
}

export interface ErrorEntry {
  id: number;
  code: string;
  signature: string;
  description: string;
  cause: string;
  fix: string;
  sql_before: string;
  sql_after: string;
  occurrences: number;
  approved: boolean;
}

export interface Accepted {
  run_id: string;
  status: string;
  message: string;
}

export type Role = "de" | "engineer" | "reviewer";

export interface CurrentUser {
  name: string;
  role: Role;
}
