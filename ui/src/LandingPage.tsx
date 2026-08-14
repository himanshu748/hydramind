import {
  ArrowRight,
  Braces,
  Check,
  ChevronDown,
  Database,
  GitBranch,
  History,
  Menu,
  Network,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";
import HydraMark from "./BrandMark";

const features = [
  {
    number: "01",
    icon: Network,
    title: "Facts become relationships",
    body: "Memories connect to entities, contradictions, revisions, and the facts they were derived from.",
  },
  {
    number: "02",
    icon: GitBranch,
    title: "Trust moves through provenance",
    body: "When a source fact changes, HydraMind lowers the confidence of dependent memories for two graph hops.",
  },
  {
    number: "03",
    icon: History,
    title: "Every score has a reason",
    body: "Agents can read when trust changed, which memory caused it, and the exact decay that was applied.",
  },
];

const tools = [
  "remember",
  "recall",
  "revise",
  "timeline",
  "trace_memory",
  "check_conflict",
  "explain_trust",
  "forget",
];

function LandingPage() {
  const [navOpen, setNavOpen] = useState(false);
  const [contradicted, setContradicted] = useState(false);
  const [openQuestion, setOpenQuestion] = useState(0);
  const [activeSection, setActiveSection] = useState("");
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.14 },
    );
    document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const sections = ["trust", "tools", "architecture", "questions"]
      .map((id) => document.getElementById(id))
      .filter((section): section is HTMLElement => section !== null);
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target.id) setActiveSection(visible.target.id);
      },
      { rootMargin: "-28% 0px -55%", threshold: [0.05, 0.25, 0.6] },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let animationFrame = 0;
    const updateProgress = () => {
      animationFrame = 0;
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      const progress = scrollable > 0 ? Math.min(window.scrollY / scrollable, 1) : 0;
      navRef.current?.style.setProperty("--page-progress", String(progress));
    };
    const handleScroll = () => {
      if (animationFrame === 0) animationFrame = window.requestAnimationFrame(updateProgress);
    };
    updateProgress();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (animationFrame !== 0) window.cancelAnimationFrame(animationFrame);
    };
  }, []);

  return (
    <div className="landing-shell">
      <header className="landing-nav" ref={navRef}>
        <a className="landing-brand" href="#top" aria-label="HydraMind home">
          <HydraMark className="landing-brand-mark" />
          <span>HydraMind</span>
        </a>
        <nav className={`landing-links ${navOpen ? "open" : ""}`} aria-label="Landing navigation">
          <a href="#trust" aria-current={activeSection === "trust" ? "location" : undefined} onClick={() => setNavOpen(false)}>How trust moves</a>
          <a href="#tools" aria-current={activeSection === "tools" ? "location" : undefined} onClick={() => setNavOpen(false)}>MCP tools</a>
          <a href="#architecture" aria-current={activeSection === "architecture" ? "location" : undefined} onClick={() => setNavOpen(false)}>Architecture</a>
          <a href="#questions" aria-current={activeSection === "questions" ? "location" : undefined} onClick={() => setNavOpen(false)}>Questions</a>
        </nav>
        <a className="landing-dashboard-link" href="/app">
          Open dashboard <ArrowRight size={16} />
        </a>
        <button
          className="landing-menu"
          type="button"
          aria-label={navOpen ? "Close navigation" : "Open navigation"}
          onClick={() => setNavOpen((open) => !open)}
        >
          {navOpen ? <X size={21} /> : <Menu size={21} />}
        </button>
      </header>

      <main id="top">
        <section className="landing-hero">
          <div className="hero-copy">
            <span className="hero-eyebrow"><i /> Persistent memory, with receipts</span>
            <h1>
              <span>Memory that</span>
              <span>knows when it</span>
              <span>may be wrong.</span>
            </h1>
            <p>
              HydraMind gives coding agents persistent graph memory that detects changed facts,
              lowers trust in downstream assumptions, and explains every revision.
            </p>
            <div className="hero-actions">
              <a className="landing-primary" href="/app">
                Explore the live graph <ArrowRight size={17} />
              </a>
              <a className="landing-secondary" href="#trust">See how trust moves</a>
            </div>
            <div className="hero-proof" aria-label="Product facts">
              <span><Database size={15} /> HydraDB over Bolt</span>
              <span><Braces size={15} /> Sessionless MCP v2</span>
              <span><ShieldCheck size={15} /> Explainable trust</span>
            </div>
          </div>

          <InteractiveTrustGraph contradicted={contradicted} onToggle={() => setContradicted((value) => !value)} />
        </section>

        <section className="statement-band reveal">
          <p>
            Similarity can find a related sentence. A graph can show which conclusions became
            less reliable after that sentence stopped being true.
          </p>
        </section>

        <section className="trust-section reveal" id="trust">
          <div className="section-heading">
            <span className="section-number">01</span>
            <div>
              <h2>Trust follows the evidence.</h2>
              <p>A contradiction is not a delete. It becomes a durable event in the memory graph.</p>
            </div>
          </div>
          <div className="trust-sequence">
            <article>
              <span className="sequence-value active">1.00</span>
              <h3>A new fact arrives</h3>
              <p>The agent stores a current claim and links it to the entities it describes.</p>
            </article>
            <ArrowRight className="sequence-arrow" aria-hidden="true" />
            <article>
              <span className="sequence-value danger">0.60</span>
              <h3>The stale claim decays</h3>
              <p>HydraMind preserves the older memory and records who contradicted it and why.</p>
            </article>
            <ArrowRight className="sequence-arrow" aria-hidden="true" />
            <article>
              <span className="sequence-value amber">0.85 / 0.70</span>
              <h3>Dependents adjust</h3>
              <p>Derived memories lose smaller amounts of trust across one and two graph hops.</p>
            </article>
          </div>
        </section>

        <section className="feature-section reveal">
          <div className="section-heading compact-heading">
            <span className="section-number">02</span>
            <div>
              <h2>The graph is the product.</h2>
              <p>Each relationship carries meaning that a flat memory index cannot express.</p>
            </div>
          </div>
          <div className="feature-list">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <article key={feature.number}>
                  <span className="feature-number">{feature.number}</span>
                  <Icon size={23} strokeWidth={1.7} />
                  <h3>{feature.title}</h3>
                  <p>{feature.body}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section className="tools-section reveal" id="tools">
          <div className="tool-copy">
            <span className="section-number">03</span>
            <h2>A small interface for durable context.</h2>
            <p>
              Coding agents get eight typed MCP tools, including explicit revision timelines and
              native evidence traces. HydraDB keeps every relationship and trust event underneath.
            </p>
            <a href="/app">Try the tools in the dashboard <ArrowRight size={16} /></a>
          </div>
          <div className="tool-ledger" aria-label="HydraMind MCP tools">
            {tools.map((tool, index) => (
              <div key={tool}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <code>{tool}</code>
                <Check size={16} />
              </div>
            ))}
          </div>
        </section>

        <section className="architecture-section reveal" id="architecture">
          <div className="section-heading">
            <span className="section-number">04</span>
            <div>
              <h2>Built directly on HydraDB.</h2>
              <p>No custom database client, embedding service, or hidden classifier is required.</p>
            </div>
          </div>
          <div className="architecture-flow">
            <div><Braces size={22} /><strong>Coding agent</strong><span>Stateless request</span></div>
            <ArrowRight aria-hidden="true" />
            <div><HydraMark className="landing-brand-mark" /><strong>HydraMind</strong><span>Python MCP v2</span></div>
            <ArrowRight aria-hidden="true" />
            <div><Database size={22} /><strong>HydraDB</strong><span>Durable graph state</span></div>
          </div>
          <pre className="cypher-sample" aria-label="Cypher relationship example"><code>{`CALL algo.SSpaths({
  sourceNode: $source,
  relTypes: ['CONTRADICTS', 'DERIVED_FROM', 'SUPERSEDED_BY'],
  relDirection: 'both', maxLen: 2
}) YIELD path RETURN path`}</code></pre>
        </section>

        <section className="questions-section reveal" id="questions">
          <div className="section-heading compact-heading">
            <span className="section-number">05</span>
            <div><h2>Questions, answered plainly.</h2></div>
          </div>
          <div className="question-list">
            {[
              ["Does MCP keep a session?", "No. HydraMind speaks sessionless MCP 2026-07-28 and forces stateless mode for legacy Streamable HTTP clients. Durable state lives in HydraDB."],
              ["Does HydraMind need Docker?", "No. The verified development path runs the official graph-node from source and connects over localhost Bolt."],
              ["Does it use embeddings?", "No. Recall currently uses scoped Cypher filtering and transparent keyword overlap multiplied by trust."],
              ["What happens when information changes?", "Agents can record uncertainty as a contradiction with trust decay, or explicitly revise a fact into a dated SUPERSEDED_BY timeline."],
            ].map(([question, answer], index) => (
              <article key={question} className={openQuestion === index ? "open" : ""}>
                <button type="button" onClick={() => setOpenQuestion(openQuestion === index ? -1 : index)} aria-expanded={openQuestion === index}>
                  <span>{question}</span><ChevronDown size={18} />
                </button>
                <div><p>{answer}</p></div>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-cta reveal">
          <HydraMark className="landing-brand-mark" />
          <h2>Inspect the graph. Change a fact. Watch trust move.</h2>
          <p>The local dashboard is connected to the same HydraDB-backed memory service exposed through MCP.</p>
          <a className="landing-primary" href="/app">Open HydraMind <ArrowRight size={17} /></a>
        </section>
      </main>

      <footer className="landing-footer reveal">
        <a className="landing-brand" href="#top"><HydraMark className="landing-brand-mark" /><span>HydraMind</span></a>
        <p>Persistent, trust-weighted memory for coding agents.</p>
        <div><a href="/app">Dashboard</a><a href="#tools">MCP tools</a><span>MIT licensed</span></div>
      </footer>
    </div>
  );
}

function InteractiveTrustGraph({ contradicted, onToggle }: { contradicted: boolean; onToggle: () => void }) {
  const graphRef = useRef<HTMLDivElement>(null);

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width) * 100;
    const y = ((event.clientY - bounds.top) / bounds.height) * 100;
    graphRef.current?.style.setProperty("--graph-x", `${x}%`);
    graphRef.current?.style.setProperty("--graph-y", `${y}%`);
  };

  const resetPointer = () => {
    graphRef.current?.style.setProperty("--graph-x", "50%");
    graphRef.current?.style.setProperty("--graph-y", "44%");
  };

  return (
    <div
      className={`hero-graph ${contradicted ? "changed" : ""}`}
      ref={graphRef}
      onPointerMove={handlePointerMove}
      onPointerLeave={resetPointer}
    >
      <div className="hero-graph-header">
        <span>Live trust cascade</span>
        <span className="hero-live"><i /> HydraDB connected</span>
      </div>
      <svg viewBox="0 0 620 430" role="img" aria-label="Interactive memory trust graph">
        <defs>
          <marker id="landing-arrow-amber" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" /></marker>
          <marker id="landing-arrow-red" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" /></marker>
        </defs>
        <g className="landing-edge contradiction-edge"><path d="M174 128 C254 128 276 128 348 128" /><text x="261" y="113">CONTRADICTS</text></g>
        <g className="landing-edge derived-one"><path d="M436 184 C436 238 356 255 316 286" /><text x="395" y="235">DERIVED_FROM</text></g>
        <g className="landing-edge derived-two"><path d="M316 335 C253 365 193 365 142 329" /><text x="231" y="378">DERIVED_FROM</text></g>
        <g className="landing-node new-node"><rect x="34" y="74" width="176" height="108" rx="9" /><circle cx="54" cy="94" r="5" /><text className="node-label" x="68" y="98">CURRENT MEMORY</text><text className="node-copy" x="54" y="126">Must not use</text><text className="node-copy" x="54" y="145">direct routing</text><text className="node-score" x="54" y="168">Trust 1.00</text></g>
        <g className="landing-node old-node"><rect x="348" y="74" width="204" height="108" rx="9" /><circle cx="368" cy="94" r="5" /><text className="node-label" x="382" y="98">OLDER MEMORY</text><text className="node-copy" x="368" y="126">Must always use</text><text className="node-copy" x="368" y="145">direct routing</text><text className="node-score" x="368" y="168">Trust {contradicted ? "0.60" : "1.00"}</text></g>
        <g className="landing-node child-node"><rect x="246" y="274" width="186" height="88" rx="9" /><circle cx="266" cy="294" r="5" /><text className="node-label" x="280" y="298">RELEASE CHECKLIST</text><text className="node-score" x="266" y="337">Trust {contradicted ? "0.85" : "1.00"}</text></g>
        <g className="landing-node grandchild-node"><rect x="38" y="274" width="166" height="88" rx="9" /><circle cx="58" cy="294" r="5" /><text className="node-label" x="72" y="298">INCIDENT RUNBOOK</text><text className="node-score" x="58" y="337">Trust {contradicted ? "0.70" : "1.00"}</text></g>
        {contradicted && (
          <g className="trust-signals" aria-hidden="true">
            <circle className="trust-signal danger-signal" r="4">
              <animateMotion dur="0.65s" fill="freeze" path="M174 128 C254 128 276 128 348 128" />
              <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.12;0.78;1" dur="0.82s" fill="freeze" />
            </circle>
            <circle className="trust-signal amber-signal" r="4">
              <animateMotion begin="0.55s" dur="0.72s" fill="freeze" path="M436 184 C436 238 356 255 316 286" />
              <animate begin="0.55s" attributeName="opacity" values="0;1;1;0" keyTimes="0;0.12;0.78;1" dur="0.9s" fill="freeze" />
            </circle>
            <circle className="trust-signal amber-signal" r="4">
              <animateMotion begin="1.12s" dur="0.72s" fill="freeze" path="M316 335 C253 365 193 365 142 329" />
              <animate begin="1.12s" attributeName="opacity" values="0;1;1;0" keyTimes="0;0.12;0.78;1" dur="0.9s" fill="freeze" />
            </circle>
          </g>
        )}
      </svg>
      <div className="hero-graph-controls">
        <p aria-live="polite">{contradicted ? "The revision is recorded. Downstream trust has changed." : "Introduce a newer, opposite routing policy."}</p>
        <button type="button" onClick={onToggle}>{contradicted ? "Reset trust" : "Introduce contradiction"}</button>
      </div>
    </div>
  );
}

export default LandingPage;
