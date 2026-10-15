export type Finding = {
  finding_id: string;
  rule_id: string;
  rule_version: string;
  subject_key: string;
  category: string;
  score: number;
  severity: string;
  status: string;
  active: boolean;
  created_at: string;
  last_evaluated_at: string;
  evidence_summary: string;
  evidence_paths: string[];
  values: Record<string, unknown>;
  record_ids: Record<string, string[]>;
  query: { name: string; params: Record<string, unknown> };
  reviews?: { action_id: string; decision: string; reviewer: string; note: string; created_at: string; previous_status: string }[];
  policy_evidence?: PolicyChunk[];
  related?: string[];
};

export type PolicyChunk = {
  chunk_id: string;
  document_id: string;
  section?: string;
  text: string;
  source?: string;
  retrieval_method?: string;
  method?: string;
  finding_ids?: string[];
};

export type ToolStep = { actor: string; tool: string; args?: Record<string, unknown>; ok: boolean; error?: string | null; ms?: number; status?: string };

export type Investigation = {
  investigation_id: string;
  question: string;
  target_id: string;
  target_label: string;
  status: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  score: number;
  severity: string;
  score_detail: { score: number; raw_points: number; capped: boolean; severity: string; breakdown: { finding_id: string; rule_id: string; points: number }[] };
  scope: { suppliers: string[]; root_suppliers: string[]; invoice_ids: string[]; po_ids: string[]; shipment_ids: string[] };
  explanation?: string;
  explanation_mode?: string;
  grounding?: { supported: boolean; ids_checked: number; numbers_checked: number; unsupported_ids: string[]; unsupported_numbers: number[]; banned_phrases: string[]; rejected_attempts: unknown[]; policy_detail?: string } | null;
  policy_status: string;
  policy_evidence: PolicyChunk[];
  tool_trace: ToolStep[];
  findings: Finding[];
  history: { previous: InvestigationSummary[]; next: InvestigationSummary[] };
};

export type InvestigationSummary = {
  investigation_id: string;
  question: string;
  target_id?: string;
  status: string;
  created_at: string;
  score: number;
  severity?: string;
  finding_count?: number;
};

export type Turn = { turn_id: string; question: string; answer: string; grounded: boolean; mode: string; created_at: string };

export type GraphData = {
  nodes: { id: string; label: string; name?: string | null }[];
  edges: { source: string; target: string; type: string }[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Record<string, unknown>>("/health"),
  stats: () => request<Record<string, any>>("/stats"),
  rules: () => request<any[]>("/rules"),
  loadDataset: (reset: boolean) => request<any>("/admin/load-dataset", { method: "POST", body: JSON.stringify({ reset }) }),
  runDetection: () => request<any>("/detect/run", { method: "POST" }),
  findings: (q: { status?: string; rule_id?: string } = {}) => {
    const params = new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][]);
    return request<Finding[]>(`/findings?${params}`);
  },
  finding: (id: string) => request<Finding>(`/findings/${id}`),
  review: (id: string, body: { decision: string; reviewer: string; note: string; investigation_id?: string }) =>
    request<any>(`/findings/${id}/review`, { method: "POST", body: JSON.stringify(body) }),
  investigations: () => request<InvestigationSummary[]>("/investigations"),
  investigation: (id: string) => request<Investigation>(`/investigations/${id}`),
  createInvestigation: (body: { question: string; entity_id?: string; created_by: string; use_llm?: boolean }) =>
    request<Investigation>("/investigations", { method: "POST", body: JSON.stringify(body) }),
  setStatus: (id: string, status: string, reviewer: string) =>
    request<Investigation>(`/investigations/${id}`, { method: "PATCH", body: JSON.stringify({ status, reviewer }) }),
  graph: (id: string) => request<GraphData>(`/investigations/${id}/graph`),
  turns: (id: string) => request<Turn[]>(`/investigations/${id}/turns`),
  ask: (id: string, question: string) => request<Turn>(`/investigations/${id}/ask`, { method: "POST", body: JSON.stringify({ question }) }),
  compare: (id: string) => request<any>(`/investigations/${id}/compare`),
};
