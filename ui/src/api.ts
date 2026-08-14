export type MemoryStatus = "active" | "contradicted" | "superseded" | "forgotten";

export type Memory = {
  id: string;
  content: string;
  source: string;
  created_at: string;
  valid_from: string;
  valid_to: string | null;
  trust_score: number;
  status: MemoryStatus;
  entities: string[];
};

export type Contradiction = {
  source: string;
  target: string;
  detected_at: string;
  reason: string;
};

export type Derivation = {
  source: string;
  target: string;
  decay_hop: number | null;
  last_decayed_at: string | null;
};

export type Revision = {
  source: string;
  target: string;
  revised_at: string;
  reason: string;
};

export type GraphState = {
  scope: string;
  memories: Memory[];
  contradictions: Contradiction[];
  derivations: Derivation[];
  revisions: Revision[];
};

export type Conflict = {
  id: string;
  content: string;
  trust_score: number;
  reason: string;
};

export type RecalledMemory = Pick<
  Memory,
  "id" | "content" | "created_at" | "trust_score" | "status"
>;

export type TimelineEntry = Pick<
  Memory,
  "id" | "content" | "created_at" | "valid_from" | "valid_to" | "trust_score" | "status"
> & {
  supersedes: string | null;
  superseded_by: string | null;
  revision_reason: string | null;
};

export type TraceNode = {
  id: string;
  kind: "Memory" | "Entity" | "Node";
  label: string;
  content: string | null;
  scope: string | null;
  status: string | null;
  trust_score: number | null;
};

export type TracePath = {
  nodes: TraceNode[];
  relationships: Array<{
    type: string;
    source_id: string;
    target_id: string;
    properties: Record<string, unknown>;
  }>;
};

export type MemoryTrace = {
  engine: string;
  memory_id: string;
  scope: string;
  max_hops: number;
  paths: TracePath[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  const body = (await response.json()) as T & { error?: string };
  if (!response.ok) {
    throw new Error(body.error || `Request failed with status ${response.status}`);
  }
  return body;
}

export const api = {
  health: () => request<{ connected: boolean }>("/api/health"),
  state: (scope: string) => request<GraphState>(`/api/state?scope=${encodeURIComponent(scope)}`),
  seedDemo: (scope: string) =>
    request<GraphState>("/api/demo", {
      method: "POST",
      body: JSON.stringify({ scope }),
    }),
  recall: (scope: string, query: string, entityRefs: string[] = []) =>
    request<{ results: RecalledMemory[] }>("/api/recall", {
      method: "POST",
      body: JSON.stringify({ scope, query, entity_refs: entityRefs, limit: 10 }),
    }),
  conflicts: (scope: string, content: string, entityRefs: string[]) =>
    request<{ conflicts: Conflict[] }>("/api/conflicts", {
      method: "POST",
      body: JSON.stringify({ scope, content, entity_refs: entityRefs }),
    }),
  remember: (
    scope: string,
    content: string,
    entityRefs: string[],
    derivedFrom: string[],
  ) =>
    request<{ memory_id: string }>("/api/remember", {
      method: "POST",
      body: JSON.stringify({
        scope,
        content,
        entity_refs: entityRefs,
        derived_from: derivedFrom,
      }),
    }),
  revise: (scope: string, memoryId: string, content: string, reason: string) =>
    request<{ memory_id: string }>("/api/revise", {
      method: "POST",
      body: JSON.stringify({ scope, memory_id: memoryId, content, reason }),
    }),
  timeline: (scope: string, entityRef: string) =>
    request<{ timeline: TimelineEntry[] }>(
      `/api/timeline?scope=${encodeURIComponent(scope)}&entity_ref=${encodeURIComponent(entityRef)}`,
    ),
  trace: (scope: string, memoryId: string) =>
    request<MemoryTrace>(
      `/api/trace?scope=${encodeURIComponent(scope)}&memory_id=${encodeURIComponent(memoryId)}`,
    ),
  explain: (scope: string, memoryId: string) =>
    request<{ chain: string[] }>(
      `/api/explain?scope=${encodeURIComponent(scope)}&memory_id=${encodeURIComponent(memoryId)}`,
    ),
  forget: (scope: string, memoryId: string) =>
    request<{ success: boolean }>("/api/forget", {
      method: "POST",
      body: JSON.stringify({ scope, memory_id: memoryId }),
    }),
};
