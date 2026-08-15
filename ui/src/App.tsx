import {
  AlertTriangle,
  ArrowDownRight,
  BookOpen,
  Braces,
  Check,
  CircleHelp,
  Database,
  GitBranch,
  History,
  LoaderCircle,
  Menu,
  Network,
  PencilLine,
  Plus,
  RefreshCw,
  Route,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Conflict, GraphState, Memory, MemoryTrace, RecalledMemory, Revision, TimelineEntry } from "./api";
import HydraMark from "./BrandMark";

type View = "memories" | "recall" | "timeline" | "graph" | "conflicts";

const emptyState: GraphState = {
  scope: "acme-platform",
  memories: [],
  contradictions: [],
  derivations: [],
  revisions: [],
};

const navigation = [
  { id: "memories" as const, label: "Memories", icon: BookOpen },
  { id: "recall" as const, label: "Recall", icon: Search },
  { id: "timeline" as const, label: "Timeline", icon: History },
  { id: "graph" as const, label: "Trust graph", icon: Network },
  { id: "conflicts" as const, label: "Conflicts", icon: AlertTriangle },
];

function App() {
  const [view, setView] = useState<View>("graph");
  const [scope, setScope] = useState("acme-platform");
  const [scopeDraft, setScopeDraft] = useState("acme-platform");
  const [graph, setGraph] = useState<GraphState>(emptyState);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [revisionTarget, setRevisionTarget] = useState<Memory | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [toast, setToast] = useState("");
  const loadSequence = useRef(0);

  const load = useCallback(async (nextScope: string) => {
    const sequence = ++loadSequence.current;
    setLoading(true);
    setError("");
    try {
      const [health, state] = await Promise.all([api.health(), api.state(nextScope)]);
      if (sequence !== loadSequence.current) return;
      setConnected(health.connected);
      setGraph(state);
      setSelectedId((current) => {
        if (current && state.memories.some((memory) => memory.id === current)) return current;
        return state.memories[0]?.id ?? null;
      });
    } catch (reason) {
      if (sequence !== loadSequence.current) return;
      setConnected(false);
      setError(reason instanceof Error ? reason.message : "Unable to load HydraMind.");
    } finally {
      if (sequence === loadSequence.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(scope);
  }, [load, scope]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(""), 3600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const selected = graph.memories.find((memory) => memory.id === selectedId) ?? null;
  const contradicted = graph.memories.filter((memory) => memory.status === "contradicted");

  async function seedDemo() {
    setLoading(true);
    setError("");
    try {
      const state = await api.seedDemo(scope);
      setGraph(state);
      setSelectedId(state.memories.find((memory) => memory.status === "contradicted")?.id ?? null);
      setToast("Demo graph created in HydraDB.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create the demo graph.");
    } finally {
      setLoading(false);
    }
  }

  async function forget(memoryId: string) {
    if (!window.confirm("Forget this memory while preserving its provenance?")) return;
    try {
      await api.forget(scope, memoryId);
      setToast("Memory forgotten. Provenance was preserved.");
      await load(scope);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to forget memory.");
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        view={view}
        connected={connected}
        open={mobileNavOpen}
        onSelect={(next) => {
          setView(next);
          setMobileNavOpen(false);
        }}
        onRemember={() => setDialogOpen(true)}
      />

      <main className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            type="button"
            aria-label="Open navigation"
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu size={20} />
          </button>
          <label className="scope-control">
            <span>Scope</span>
            <input
              value={scopeDraft}
              onChange={(event) => setScopeDraft(event.target.value)}
              onBlur={() => {
                const nextScope = scopeDraft.trim();
                if (nextScope) setScope(nextScope);
                else setScopeDraft(scope);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  const nextScope = scopeDraft.trim();
                  if (nextScope) setScope(nextScope);
                }
              }}
              aria-label="Memory scope"
            />
          </label>
          <div className={`connection ${connected ? "connected" : "disconnected"}`}>
            <span className="connection-dot" aria-hidden="true" />
            <span>{connected ? "HydraDB connected" : "HydraDB unavailable"}</span>
          </div>
          <button className="secondary-button compact" type="button" onClick={() => void load(scope)}>
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            Refresh
          </button>
        </header>

        {error ? (
          <ErrorBanner message={error} onRetry={() => void load(scope)} />
        ) : null}

        {loading && graph.memories.length === 0 ? (
          <LoadingScreen />
        ) : graph.memories.length === 0 ? (
          <EmptyGraph onSeed={() => void seedDemo()} onRemember={() => setDialogOpen(true)} />
        ) : (
          <div className="content-stage">
            {view === "graph" ? (
              <GraphView
                graph={graph}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onRemember={() => setDialogOpen(true)}
              />
            ) : null}
            {view === "memories" ? (
              <MemoryView
                memories={graph.memories}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onForget={(id) => void forget(id)}
                onRemember={() => setDialogOpen(true)}
              />
            ) : null}
            {view === "conflicts" ? (
              <ConflictView memories={contradicted} onSelect={(id) => {
                setSelectedId(id);
                setView("graph");
              }} />
            ) : null}
            {view === "recall" ? (
              <RecallView scope={scope} memories={graph.memories} onSelect={setSelectedId} />
            ) : null}
            {view === "timeline" ? (
              <TimelineView
                scope={scope}
                memories={graph.memories}
                revisions={graph.revisions}
                onSelect={(id) => {
                  setSelectedId(id);
                  setView("graph");
                }}
              />
            ) : null}

            {view === "graph" && selected ? (
              <Inspector
                scope={scope}
                memory={selected}
                onClose={() => setSelectedId(null)}
                onForget={() => void forget(selected.id)}
                onRevise={() => setRevisionTarget(selected)}
              />
            ) : null}
          </div>
        )}
      </main>

      {dialogOpen ? (
        <RememberDialog
          scope={scope}
          memories={graph.memories}
          onClose={() => setDialogOpen(false)}
          onStored={async () => {
            setDialogOpen(false);
            setToast("Memory stored in HydraDB.");
            await load(scope);
          }}
        />
      ) : null}

      {revisionTarget ? (
        <ReviseDialog
          scope={scope}
          memory={revisionTarget}
          onClose={() => setRevisionTarget(null)}
          onRevised={async (memoryId) => {
            setRevisionTarget(null);
            setToast("Revision linked. The previous fact remains auditable.");
            await load(scope);
            setSelectedId(memoryId);
          }}
        />
      ) : null}

      {mobileNavOpen ? (
        <button
          className="nav-scrim"
          type="button"
          aria-label="Close navigation"
          onClick={() => setMobileNavOpen(false)}
        />
      ) : null}

      {toast ? (
        <div className="toast" role="status">
          <Check size={17} />
          {toast}
        </div>
      ) : null}
    </div>
  );
}

function Sidebar({
  view,
  connected,
  open,
  onSelect,
  onRemember,
}: {
  view: View;
  connected: boolean;
  open: boolean;
  onSelect: (view: View) => void;
  onRemember: () => void;
}) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Primary navigation">
      <div className="brand">
        <HydraMark />
        <span>HydraMind</span>
        <button className="icon-button nav-close" type="button" aria-label="Close navigation" onClick={() => onSelect(view)}>
          <X size={20} />
        </button>
      </div>
      <nav className="nav-list">
        {navigation.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              type="button"
              onClick={() => onSelect(item.id)}
              aria-current={view === item.id ? "page" : undefined}
            >
              <Icon size={20} strokeWidth={1.8} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidebar-spacer" />
      <button className="primary-button sidebar-action" type="button" onClick={onRemember}>
        <Plus size={18} />
        <span>Remember memory</span>
      </button>
      <div className="sidebar-meta">
        <div><Database size={15} /> Bolt 7687</div>
        <div><Braces size={15} /> Sessionless MCP v2</div>
        <div><span className={`mini-dot ${connected ? "online" : ""}`} /> {connected ? "Live graph" : "Offline"}</div>
      </div>
      <span className="version">HydraMind 0.3.0</span>
    </aside>
  );
}

function GraphView({
  graph,
  selectedId,
  onSelect,
  onRemember,
}: {
  graph: GraphState;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRemember: () => void;
}) {
  const [fitKey, setFitKey] = useState(0);
  const nodes = useMemo(() => layoutNodes(graph.memories), [graph.memories, fitKey]);
  const canvasHeight = Math.max(500, Math.ceil(nodes.length / 4) * 180 + 60);
  return (
    <section className="graph-panel">
      <div className="view-heading">
        <div>
          <h1>Trust graph</h1>
          <p>See what changed, what depends on it, and why trust moved.</p>
        </div>
        <div className="heading-actions">
          <button className="secondary-button" type="button" onClick={() => setFitKey((key) => key + 1)}>
            <RefreshCw size={16} /> Fit graph
          </button>
          <button className="primary-button" type="button" onClick={onRemember}>
            <Plus size={17} /> Remember memory
          </button>
        </div>
      </div>
      <div className="graph-canvas" key={fitKey}>
        <div className="graph-world" style={{ height: `${canvasHeight}px` }}>
        <svg className="edge-layer" style={{ height: `${canvasHeight}px` }} viewBox={`0 0 900 ${canvasHeight}`} role="img" aria-label="Memory trust relationships">
          <defs>
            <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="var(--danger)" />
            </marker>
            <marker id="arrow-amber" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="var(--amber)" />
            </marker>
            <marker id="arrow-revision" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="var(--accent)" />
            </marker>
          </defs>
          {graph.contradictions.map((edge) => (
            <GraphEdge key={`${edge.source}-${edge.target}`} edge={edge} nodes={nodes} kind="contradiction" />
          ))}
          {graph.derivations.map((edge) => (
            <GraphEdge key={`${edge.source}-${edge.target}`} edge={edge} nodes={nodes} kind="derivation" />
          ))}
          {graph.revisions.map((edge) => (
            <GraphEdge key={`${edge.source}-${edge.target}`} edge={edge} nodes={nodes} kind="revision" />
          ))}
        </svg>
        <div className="canvas-grid" aria-hidden="true" />
        {nodes.map((node) => (
          <button
            type="button"
            key={node.memory.id}
            className={`memory-node ${node.memory.status} ${selectedId === node.memory.id ? "selected" : ""}`}
            style={{ left: `${node.x}px`, top: `${node.y}px` }}
            onClick={() => onSelect(node.memory.id)}
            aria-label={`${node.memory.content}, trust ${node.memory.trust_score.toFixed(2)}`}
          >
            <span className="node-kicker"><span className="node-dot" /> Memory {shortId(node.memory.id)}</span>
            <strong>{node.memory.content}</strong>
            <span className="node-trust">Trust <b>{node.memory.trust_score.toFixed(2)}</b></span>
            <span className="node-time">{relativeTime(node.memory.created_at)}</span>
          </button>
        ))}
        </div>
      </div>
      <div className="mobile-node-list">
        {graph.memories.map((memory) => (
          <button
            key={memory.id}
            type="button"
            className={`mobile-memory-row ${selectedId === memory.id ? "selected" : ""}`}
            onClick={() => onSelect(memory.id)}
          >
            <span className={`status-line ${memory.status}`} />
            <span><strong>{memory.content}</strong><small>{memory.entities.join(", ") || "No entity"}</small></span>
            <b>{memory.trust_score.toFixed(2)}</b>
          </button>
        ))}
      </div>
      <RecallRail
        key={graph.scope}
        scope={graph.scope}
        memories={graph.memories}
        onSelect={onSelect}
      />
    </section>
  );
}

type PositionedNode = { memory: Memory; x: number; y: number };

function GraphEdge({
  edge,
  nodes,
  kind,
}: {
  edge: { source: string; target: string };
  nodes: PositionedNode[];
  kind: "contradiction" | "derivation" | "revision";
}) {
  const source = nodes.find((node) => node.memory.id === edge.source);
  const target = nodes.find((node) => node.memory.id === edge.target);
  if (!source || !target) return null;
  const startX = source.x + 90;
  const startY = source.y + 62;
  const endX = target.x + 90;
  const endY = target.y + 62;
  const labelX = (startX + endX) / 2;
  const labelY = (startY + endY) / 2 - 8;
  return (
    <g className={`graph-edge ${kind}`}>
      <path
        d={`M ${startX} ${startY} C ${startX} ${(startY + endY) / 2}, ${endX} ${(startY + endY) / 2}, ${endX} ${endY}`}
        markerEnd={`url(#arrow-${kind === "contradiction" ? "red" : kind === "derivation" ? "amber" : "revision"})`}
      />
      <text x={labelX} y={labelY}>
        {kind === "contradiction" ? "CONTRADICTS" : kind === "derivation" ? "DERIVED_FROM" : "SUPERSEDED_BY"}
      </text>
    </g>
  );
}

function Inspector({
  scope,
  memory,
  onClose,
  onForget,
  onRevise,
}: {
  scope: string;
  memory: Memory;
  onClose: () => void;
  onForget: () => void;
  onRevise: () => void;
}) {
  const [chain, setChain] = useState<string[]>([]);
  const [trace, setTrace] = useState<MemoryTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setChain([]);
    setTrace(null);
    setError("");
  }, [memory.id]);

  async function explain() {
    setLoading(true);
    setError("");
    try {
      const result = await api.explain(scope, memory.id);
      setChain(result.chain);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to explain trust.");
    } finally {
      setLoading(false);
    }
  }

  async function traceEvidence() {
    setLoading(true);
    setError("");
    try {
      setTrace(await api.trace(scope, memory.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to trace graph evidence.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <aside className="inspector" aria-label="Selected memory details">
      <div className="inspector-heading">
        <div>
          <span className={`status-label ${memory.status}`}>{memory.status}</span>
          <h2>{memory.entities[0] ? humanize(memory.entities[0]) : "Memory detail"}</h2>
        </div>
        <button className="icon-button" type="button" aria-label="Close memory details" onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      <dl className="memory-facts">
        <div><dt>Memory ID</dt><dd>{shortId(memory.id)}</dd></div>
        <div><dt>Trust</dt><dd className={memory.status === "contradicted" ? "danger-text" : "trust-text"}>{memory.trust_score.toFixed(2)}</dd></div>
        <div><dt>Source</dt><dd>{memory.source}</dd></div>
      </dl>
      <div className="inspector-section">
        <h3>Body</h3>
        <p className="memory-body">{memory.content}</p>
      </div>
      <div className="inspector-section">
        <h3>Entities</h3>
        {memory.entities.length ? (
          <div className="entity-list">{memory.entities.map((entity) => <code key={entity}>{entity}</code>)}</div>
        ) : <p className="muted">No entities linked.</p>}
      </div>
      <div className="inspector-section">
        <h3>Temporal validity</h3>
        <time className="mono" dateTime={memory.valid_from}>From {formatDate(memory.valid_from)}</time>
        {memory.valid_to ? (
          <time className="mono" dateTime={memory.valid_to}>Until {formatDate(memory.valid_to)}</time>
        ) : (
          <span className="current-fact">{memory.status === "active" ? "Current fact" : "No explicit validity end"}</span>
        )}
      </div>
      {chain.length ? (
        <div className="trust-history">
          <h3>Trust history</h3>
          <ol>{chain.map((event, index) => <li key={`${event}-${index}`}>{event}</li>)}</ol>
        </div>
      ) : null}
      {trace ? (
        <div className="trace-card">
          <div><Route size={17} /><h3>Native evidence trace</h3></div>
          <p><strong>{trace.paths.length}</strong> hydrated path{trace.paths.length === 1 ? "" : "s"} · {trace.engine}</p>
          <div className="trace-relations">
            {[...new Set(trace.paths.flatMap((path) => path.relationships.map((edge) => edge.type)))].map((type) => <code key={type}>{type}</code>)}
          </div>
        </div>
      ) : null}
      {error ? <p className="inline-error">{error}</p> : null}
      <div className="inspector-actions">
        <button className="primary-button full" type="button" onClick={() => void explain()} disabled={loading}>
          {loading ? <LoaderCircle className="spin" size={17} /> : <History size={17} />}
          {loading ? "Explaining trust" : "Explain trust"}
        </button>
        <button className="secondary-button full" type="button" onClick={() => void traceEvidence()} disabled={loading}>
          <Route size={17} /> Trace native paths
        </button>
        {memory.status === "active" ? (
          <button className="secondary-button full" type="button" onClick={onRevise}>
            <PencilLine size={17} /> Revise fact
          </button>
        ) : null}
        <button className="text-button danger" type="button" onClick={onForget}>
          <Trash2 size={16} /> Forget memory
        </button>
      </div>
    </aside>
  );
}

function RecallRail({ scope, memories, onSelect }: { scope: string; memories: Memory[]; onSelect: (id: string) => void }) {
  const defaultQuery = memories.some((memory) => memory.content.toLowerCase().includes("routing"))
    ? "How should production route?"
    : "What should the agent remember?";
  const [query, setQuery] = useState(defaultQuery);
  const [results, setResults] = useState<RecalledMemory[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const visibleResults = results.flatMap((result) => {
    const memory = memories.find((candidate) => candidate.id === result.id);
    return memory ? [memory] : [];
  });

  async function recall(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await api.recall(scope, query);
      setResults(response.results);
      setSearched(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Recall failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="recall-rail" aria-labelledby="recall-heading">
      <form className="recall-form" onSubmit={(event) => void recall(event)}>
        <label htmlFor="recall-query" id="recall-heading">Recall</label>
        <div className="search-field">
          <Search size={17} />
          <input
            id="recall-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ask your memory graph"
          />
        </div>
        <button className="primary-button" type="submit" disabled={loading || !query.trim()}>
          {loading ? <LoaderCircle className="spin" size={17} /> : <Search size={17} />}
          {loading ? "Recalling" : "Recall"}
        </button>
      </form>
      {error ? <p className="inline-error">{error}</p> : null}
      <div className="recall-results" aria-live="polite">
        {visibleResults.map((memory) => (
          <button className={`recall-row ${memory.status}`} type="button" key={memory.id} onClick={() => onSelect(memory.id)}>
            <span><strong>{memory.content}</strong><small>{memory.entities.join(", ") || memory.source}</small></span>
            <b>{memory.trust_score.toFixed(2)}</b>
            <ArrowDownRight size={17} />
          </button>
        ))}
        {searched && visibleResults.length === 0 ? (
          <div className="empty-recall"><CircleHelp size={22} /><span><strong>No matching memory.</strong> Try another query or scope.</span></div>
        ) : null}
      </div>
    </section>
  );
}

function RecallView({ scope, memories, onSelect }: { scope: string; memories: Memory[]; onSelect: (id: string) => void }) {
  return (
    <section className="open-view recall-view">
      <div className="view-heading"><div><h1>Recall</h1><p>Retrieve scoped evidence ranked by relevance and trust.</p></div></div>
      <RecallRail key={scope} scope={scope} memories={memories} onSelect={onSelect} />
      <div className="recall-guide">
        <Search size={28} />
        <h2>Ask a precise question</h2>
        <p>HydraMind returns an empty result when the graph has no matching evidence.</p>
      </div>
    </section>
  );
}

function TimelineView({
  scope,
  memories,
  revisions,
  onSelect,
}: {
  scope: string;
  memories: Memory[];
  revisions: Revision[];
  onSelect: (id: string) => void;
}) {
  const entities = useMemo(
    () => [...new Set(memories.flatMap((memory) => memory.entities))].sort(),
    [memories],
  );
  const [entity, setEntity] = useState(entities[0] ?? "");
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!entities.includes(entity)) setEntity(entities[0] ?? "");
  }, [entities, entity]);

  useEffect(() => {
    if (!entity) {
      setTimeline([]);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    void api.timeline(scope, entity)
      .then((result) => {
        if (active) setTimeline(result.timeline);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load timeline.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [entity, scope]);

  return (
    <section className="open-view timeline-view">
      <div className="view-heading">
        <div><h1>Entity timeline</h1><p>Follow facts as they change without erasing what agents knew before.</p></div>
        <div className="timeline-metric"><History size={17} /><strong>{revisions.length}</strong><span>revision edges</span></div>
      </div>
      <label className="timeline-picker">
        <span>Entity</span>
        <select value={entity} onChange={(event) => setEntity(event.target.value)}>
          {entities.map((item) => <option value={item} key={item}>{item}</option>)}
        </select>
      </label>
      {error ? <p className="inline-error">{error}</p> : null}
      {loading ? <div className="timeline-loading"><LoaderCircle className="spin" size={18} /> Reading chronology</div> : null}
      <div className="timeline-track" aria-live="polite">
        {timeline.map((entry, index) => (
          <button className={`timeline-entry ${entry.status}`} type="button" key={entry.id} onClick={() => onSelect(entry.id)}>
            <span className="timeline-index">{String(index + 1).padStart(2, "0")}</span>
            <span className="timeline-copy">
              <small>{formatDate(entry.valid_from)}</small>
              <strong>{entry.content}</strong>
              {entry.revision_reason ? <em>{entry.revision_reason}</em> : <em>Original recorded fact</em>}
            </span>
            <span className={`status-label ${entry.status}`}>{entry.status}</span>
            {index < timeline.length - 1 ? <span className="timeline-connector"><ArrowDownRight size={18} /></span> : null}
          </button>
        ))}
        {!loading && timeline.length === 0 ? (
          <div className="quiet-empty"><History size={24} /><h2>No history for this entity</h2><p>Choose another linked entity or revise an active fact.</p></div>
        ) : null}
      </div>
    </section>
  );
}

function MemoryView({
  memories,
  selectedId,
  onSelect,
  onForget,
  onRemember,
}: {
  memories: Memory[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onForget: (id: string) => void;
  onRemember: () => void;
}) {
  const [filter, setFilter] = useState("");
  const visible = memories.filter((memory) => memory.content.toLowerCase().includes(filter.toLowerCase()));
  return (
    <section className="open-view">
      <div className="view-heading">
        <div><h1>Memories</h1><p>Inspect durable facts without losing their revision history.</p></div>
        <button className="primary-button" type="button" onClick={onRemember}><Plus size={17} /> Remember memory</button>
      </div>
      <label className="filter-field"><Search size={17} /><input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter memories" /></label>
      <div className="memory-table" role="table" aria-label="Memories">
        <div className="memory-table-head" role="row"><span>Memory</span><span>Status</span><span>Trust</span><span>Created</span><span /></div>
        {visible.map((memory) => (
          <div className={`memory-table-row ${selectedId === memory.id ? "selected" : ""}`} role="row" key={memory.id}>
            <button className="memory-row-select" type="button" onClick={() => onSelect(memory.id)}>
              <span><strong>{memory.content}</strong><small>{memory.entities.join(", ") || "No entity"}</small></span>
              <span className={`status-label ${memory.status}`}>{memory.status}</span>
              <b className="mono">{memory.trust_score.toFixed(2)}</b>
              <time>{relativeTime(memory.created_at)}</time>
            </button>
            <span className="row-actions"><button className="icon-button" type="button" aria-label="Forget memory" onClick={() => onForget(memory.id)}><Trash2 size={16} /></button></span>
          </div>
        ))}
      </div>
    </section>
  );
}

function ConflictView({ memories, onSelect }: { memories: Memory[]; onSelect: (id: string) => void }) {
  return (
    <section className="open-view">
      <div className="view-heading"><div><h1>Conflicts</h1><p>Review stale claims that remain preserved for audit.</p></div></div>
      {memories.length ? (
        <div className="conflict-list">
          {memories.map((memory, index) => (
            <button className="conflict-row" type="button" key={memory.id} onClick={() => onSelect(memory.id)}>
              <span className="conflict-index">{String(index + 1).padStart(2, "0")}</span>
              <span><strong>{memory.content}</strong><small>{memory.entities.join(", ")}</small></span>
              <span className="decay-readout"><small>Current trust</small><b>{memory.trust_score.toFixed(2)}</b></span>
              <ArrowDownRight size={19} />
            </button>
          ))}
        </div>
      ) : (
        <div className="quiet-empty"><Check size={24} /><h2>No contradicted memories</h2><p>This scope has no stale claims to review.</p></div>
      )}
    </section>
  );
}

function RememberDialog({
  scope,
  memories,
  onClose,
  onStored,
}: {
  scope: string;
  memories: Memory[];
  onClose: () => void;
  onStored: () => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [content, setContent] = useState("");
  const [entities, setEntities] = useState("");
  const [derivedFrom, setDerivedFrom] = useState("");
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [checking, setChecking] = useState(false);
  const [storing, setStoring] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.showModal();
    const close = () => onClose();
    dialog.addEventListener("cancel", close);
    return () => dialog.removeEventListener("cancel", close);
  }, [onClose]);

  const entityRefs = splitValues(entities);
  const derivedIds = splitValues(derivedFrom);

  async function check(event: FormEvent) {
    event.preventDefault();
    setError("");
    setChecking(true);
    try {
      const response = await api.conflicts(scope, content, entityRefs);
      setConflicts(response.conflicts);
      if (response.conflicts.length === 0) await store();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Conflict check failed.");
    } finally {
      setChecking(false);
    }
  }

  async function store() {
    setStoring(true);
    setError("");
    try {
      await api.remember(scope, content, entityRefs, derivedIds);
      await onStored();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to store memory.");
    } finally {
      setStoring(false);
    }
  }

  return (
    <dialog ref={dialogRef} className="remember-dialog" onClose={onClose}>
      <div className="dialog-heading">
        <div><h2>Remember memory</h2><p>Store a durable fact and connect its provenance.</p></div>
        <button className="icon-button" type="button" aria-label="Close dialog" onClick={onClose}><X size={19} /></button>
      </div>
      <form onSubmit={(event) => void check(event)}>
        <label className="field-label">Content<textarea autoFocus value={content} onChange={(event) => { setContent(event.target.value); setConflicts([]); }} placeholder="State one durable fact" rows={4} required /></label>
        <div className="field-grid">
          <label className="field-label">Scope<input value={scope} disabled /></label>
          <label className="field-label">Entity references<input value={entities} onChange={(event) => { setEntities(event.target.value); setConflicts([]); }} placeholder="deploy-policy, routing" required /></label>
        </div>
        <label className="field-label">Derived from<input value={derivedFrom} onChange={(event) => setDerivedFrom(event.target.value)} placeholder="Optional memory IDs, separated by commas" /><small>Optional source memories that support this fact.</small></label>
        {derivedIds.length ? (
          <div className="derived-preview"><GitBranch size={17} /><span>{derivedIds.length} provenance link{derivedIds.length === 1 ? "" : "s"} will be created.</span></div>
        ) : null}
        {conflicts.length ? (
          <div className="conflict-preview" role="alert">
            <div className="conflict-preview-title"><AlertTriangle size={18} /><strong>Potential conflict</strong></div>
            {conflicts.map((conflict) => (
              <div className="conflict-preview-row" key={conflict.id}>
                <p>{conflict.content}</p>
                <b>{conflict.trust_score.toFixed(2)}</b>
                <small>{conflict.reason}</small>
              </div>
            ))}
            <p className="conflict-note">The new memory will still be stored. Older claims will lose trust and retain a contradiction edge.</p>
          </div>
        ) : null}
        {error ? <p className="inline-error">{error}</p> : null}
        <div className="dialog-actions">
          <button className="secondary-button" type="button" onClick={onClose}>Cancel</button>
          {conflicts.length ? (
            <button className="danger-button" type="button" onClick={() => void store()} disabled={storing}>
              {storing ? <LoaderCircle className="spin" size={17} /> : <GitBranch size={17} />}
              {storing ? "Remembering" : "Remember and link contradiction"}
            </button>
          ) : (
            <button className="primary-button" type="submit" disabled={checking || storing || !content.trim() || !entityRefs.length}>
              {checking ? <LoaderCircle className="spin" size={17} /> : <Braces size={17} />}
              {checking ? "Checking conflicts" : "Check and remember"}
            </button>
          )}
        </div>
      </form>
      {memories.length ? <p className="dialog-footnote">{memories.length} existing memories in this scope.</p> : null}
    </dialog>
  );
}

function ReviseDialog({
  scope,
  memory,
  onClose,
  onRevised,
}: {
  scope: string;
  memory: Memory;
  onClose: () => void;
  onRevised: (memoryId: string) => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [content, setContent] = useState(memory.content);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.showModal();
    const close = () => onClose();
    dialog.addEventListener("cancel", close);
    return () => dialog.removeEventListener("cancel", close);
  }, [onClose]);

  async function revise(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const result = await api.revise(scope, memory.id, content, reason);
      await onRevised(result.memory_id);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "Unable to revise memory.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <dialog ref={dialogRef} className="remember-dialog revise-dialog" onClose={onClose}>
      <div className="dialog-heading">
        <div><h2>Revise fact</h2><p>Create a current fact while preserving this version in the graph.</p></div>
        <button className="icon-button" type="button" aria-label="Close dialog" onClick={onClose}><X size={19} /></button>
      </div>
      <form onSubmit={(event) => void revise(event)}>
        <div className="revision-origin"><span>Revising</span><p>{memory.content}</p></div>
        <label className="field-label">New content<textarea autoFocus value={content} onChange={(event) => setContent(event.target.value)} rows={4} required /></label>
        <label className="field-label">Why did it change?<input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="The release calendar changed" required /></label>
        <div className="derived-preview"><History size={17} /><span>Entities are inherited. A dated SUPERSEDED_BY edge will link both facts.</span></div>
        {error ? <p className="inline-error">{error}</p> : null}
        <div className="dialog-actions">
          <button className="secondary-button" type="button" onClick={onClose}>Cancel</button>
          <button className="primary-button" type="submit" disabled={saving || !content.trim() || !reason.trim()}>
            {saving ? <LoaderCircle className="spin" size={17} /> : <PencilLine size={17} />}
            {saving ? "Linking revision" : "Create revision"}
          </button>
        </div>
      </form>
    </dialog>
  );
}

function EmptyGraph({ onSeed, onRemember }: { onSeed: () => void; onRemember: () => void }) {
  return (
    <section className="empty-graph">
      <div className="empty-illustration" aria-hidden="true"><EmptyGraphMark /></div>
      <h1>Your memory graph is clear.</h1>
      <p>Store the first durable fact, or create a small routing-policy graph to explore trust propagation.</p>
      <div><button className="primary-button" type="button" onClick={onRemember}><Plus size={17} /> Remember first memory</button><button className="secondary-button" type="button" onClick={onSeed}><Sparkles size={17} /> Create demo graph</button></div>
    </section>
  );
}

function LoadingScreen() {
  return <div className="loading-screen" role="status"><LoaderCircle className="spin" size={28} /><strong>Reading the trust graph</strong><span>Connecting to HydraDB over Bolt.</span></div>;
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="error-banner" role="alert"><AlertTriangle size={18} /><span><strong>HydraMind could not load.</strong> {message}</span><button className="secondary-button compact" type="button" onClick={onRetry}>Try again</button></div>;
}

function EmptyGraphMark() {
  return <svg viewBox="0 0 240 150"><path d="M50 76L113 42L182 74L133 120L50 76Z" /><circle cx="50" cy="76" r="13" /><circle cx="113" cy="42" r="13" /><circle cx="182" cy="74" r="13" /><circle cx="133" cy="120" r="13" /></svg>;
}

function layoutNodes(memories: Memory[]): PositionedNode[] {
  const ordered = [...memories].sort((a, b) => {
    const status = Number(a.status === "contradicted") - Number(b.status === "contradicted");
    return status || b.trust_score - a.trust_score;
  });
  return ordered.map((memory, index) => ({
    memory,
    x: 40 + (index % 4) * 220,
    y: 36 + Math.floor(index / 4) * 180,
  }));
}

function splitValues(value: string) {
  return value.split(",").map((part) => part.trim()).filter(Boolean);
}

function shortId(value: string) {
  return `${value.slice(0, 6)}…${value.slice(-3)}`;
}

function humanize(value: string) {
  return value.split(/[-_]/).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function relativeTime(value: string) {
  const timestamp = new Date(value).valueOf();
  if (Number.isNaN(timestamp)) return value;
  const minutes = Math.max(0, Math.round((Date.now() - timestamp) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default App;
