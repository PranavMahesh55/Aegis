const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accentColor": "#B63A2F",
  "trustColor": "#19715B",
  "density": 0.92,
  "motionSpeed": 1,
  "canvasMaxWidth": "1840px"
}/*EDITMODE-END*/;

const INCIDENT_ID = "aegis-4821";
const steps = ["Healthy", "Changed", "Blocked", "Remediated"];

const basePipelines = [
  { id: "refund", name: "Refund Resolution Agent", version: "v2.8.4", owner: "Commerce AI Platform", env: "Production", defaultTrust: "blocked", source: "refund-policy-q4-draft.md", context: "Refund RAG index", agent: "Refund Resolution Agent", action: "issue_refund", actionDetail: "issue_refund · monetary · max $10,000", change: "Unapproved refund-policy source entered context", summary: "Unapproved policy source changed the context path for a monetary tool.", incidentId: INCIDENT_ID, datahub: ["Document entity", "Approval state", "RAG lineage edge", "Tool dependency", "Ownership", "Change event"], aegis: ["Affected path selected", "ApprovedContextSource failed", "$8,500 tool call blocked", "Restore approved policy source"], recent: ["docs-sync MCP replaced refund-policy-v12.md", "Approval state: not approved", "Affected agent path confirmed"] },
  { id: "risk", name: "Account Risk Agent", version: "v3.1.0", owner: "Trust Operations", env: "Production", defaultTrust: "review", source: "risk_features_​daily", context: "Account risk feature view", agent: "Account Risk Agent", action: "freeze_account", actionDetail: "freeze_account · account restriction", change: "Feature freshness breached review threshold", summary: "Feature freshness breached review threshold before account restriction.", datahub: ["Feature view", "Freshness assertion", "Owner", "Tool dependency"], aegis: ["Review decision", "Freshness warning", "Human approval required"], recent: ["Feature job missed 04:00 UTC SLA", "Owner notified", "Restriction tool held for review"] },
  { id: "support", name: "Customer Support Agent", version: "v4.6.2", owner: "CX Automation", env: "Production", defaultTrust: "trusted", source: "kb-shipping-v19.md", context: "Support retrieval index", agent: "Customer Support Agent", action: "create_ticket", actionDetail: "create_ticket / escalate_case", change: "Approved shipping knowledge current", summary: "Approved support knowledge and regression scenarios are current.", datahub: ["Knowledge source", "Index lineage", "Ownership"], aegis: ["Allow decision", "Regression suite passed", "Attestation current"], recent: ["Shipping policy approved", "Escalation skill unchanged", "Regression scenarios passed"] },
  { id: "claims", name: "Claims Triage Agent", version: "v1.9.7", owner: "Claims Platform", env: "Production", defaultTrust: "trusted", source: "claims-procedure-v8.md", context: "Claims triage index", agent: "Claims Triage Agent", action: "route_claim", actionDetail: "route_claim · workflow assignment", change: "Procedure source verified", summary: "Claims routing context remains approved and traceable.", datahub: ["Procedure document", "Index lineage", "Skill dependency"], aegis: ["Allow decision", "Context source verified", "No exposed monetary action"], recent: ["Procedure v8 approved", "Routing skill unchanged", "Nightly regression passed"] }
];

function App() {
  const [activeView, setActiveView] = React.useState("command");
  const [selectedPipelineId, setSelectedPipelineId] = React.useState("refund");
  const [incidentStep, setIncidentStep] = React.useState(2);
  const [evidenceOpen, setEvidenceOpen] = React.useState(false);
  const [incidentResolved, setIncidentResolved] = React.useState(false);

  const pipelines = React.useMemo(() => basePipelines.map((pipeline) => {
    if (pipeline.id !== "refund") return pipeline;
    const computedTrust = incidentResolved ? "trusted" : incidentStep >= 2 ? "blocked" : incidentStep === 1 ? "review" : "trusted";
    const change = incidentResolved ? "Approved refund-policy-v12.md restored" : pipeline.change;
    return { ...pipeline, computedTrust, change };
  }), [incidentStep, incidentResolved]);

  const selectedPipeline = pipelines.find((pipeline) => pipeline.id === selectedPipelineId) || pipelines[0];
  const openPipeline = (id) => { setSelectedPipelineId(id); setActiveView("pipelines"); };
  const openIncident = () => { setSelectedPipelineId("refund"); setActiveView("incidents"); };
  const verifyRecovery = () => { setIncidentResolved(true); setIncidentStep(3); setEvidenceOpen(false); setActiveView("command"); };
  const resetSimulation = () => { setIncidentResolved(false); setIncidentStep(0); setEvidenceOpen(false); setSelectedPipelineId("refund"); setActiveView("incidents"); };

  return <main className="aegis-app">
    <style>{styles}</style>
    <AppShell activeView={activeView} setActiveView={setActiveView} selectedPipeline={selectedPipeline} incidentResolved={incidentResolved} />
    {activeView === "command" && <CommandCenter pipelines={pipelines} openPipeline={openPipeline} openIncident={openIncident} incidentResolved={incidentResolved} />}
    {activeView === "pipelines" && <PipelineDetail pipeline={selectedPipeline} openPipeline={openPipeline} openIncident={openIncident} incidentStep={incidentStep} incidentResolved={incidentResolved} />}
    {activeView === "incidents" && <IncidentWorkspace incidentStep={incidentStep} setIncidentStep={setIncidentStep} evidenceOpen={evidenceOpen} setEvidenceOpen={setEvidenceOpen} openPipeline={() => openPipeline("refund")} verifyRecovery={verifyRecovery} resetSimulation={resetSimulation} incidentResolved={incidentResolved} />}
    {activeView === "controls" && <ControlsView openIncident={openIncident} incidentResolved={incidentResolved} />}
  </main>;
}

function AppShell({ activeView, setActiveView, selectedPipeline, incidentResolved }) {
  const views = [["command", "Command Center"], ["pipelines", "Pipelines"], ["incidents", "Incidents"], ["controls", "Controls"]];
  return <header className="topbar paper-panel">
    <button className="brand" onClick={() => setActiveView("command")} aria-label="Open Command Center"><span className="brand-mark">AG</span><span><strong>Aegis</strong><em>Runtime context safety</em></span></button>
    <nav aria-label="Primary navigation">{views.map(([id, label]) => <button key={id} className={activeView === id ? "active" : ""} onClick={() => setActiveView(id)}>{label}</button>)}</nav>
    <div className="connection"><StatusGlyph tone="trusted" /><span>DataHub production connected</span><code>urn:li:dataPlatform:aegis-prod</code></div>
    <div className="context-line"><span>{selectedPipeline.name}</span><span>{selectedPipeline.env}</span><span>{INCIDENT_ID}</span><TrustBadge tone={incidentResolved ? "trusted" : selectedPipeline.computedTrust || selectedPipeline.defaultTrust} /></div>
  </header>;
}

function CommandCenter({ pipelines, openPipeline, openIncident, incidentResolved }) {
  return <section className="view command-view" aria-labelledby="command-heading">
    <div className="hero-row">
      <div className="view-heading"><p className="eyebrow">Production Command Center</p><h1 id="command-heading">Monitor context safety across live agent pipelines.</h1><p>DataHub supplies relationships and governance evidence. Aegis evaluates affected paths and blocks unsafe consequential actions before execution.</p></div>
      <div className="operator-note paper-panel"><strong>{incidentResolved ? "Refund pipeline restored to trusted." : "Investigate Refund Resolution Agent first."}</strong><span>{incidentResolved ? "Incident aegis-4821 resolved and written back to DataHub." : "Unapproved refund-policy source exposed issue_refund before execution."}</span><button className="primary" onClick={incidentResolved ? () => openPipeline("refund") : openIncident}>{incidentResolved ? "Review restored pipeline" : "Open incident"}</button></div>
    </div>
    <div className="pipeline-lanes" aria-label="Production agent pipelines">{pipelines.map((pipeline) => <PipelineLane key={pipeline.id} pipeline={pipeline} onSelect={() => openPipeline(pipeline.id)} />)}</div>
  </section>;
}

function PipelineLane({ pipeline, onSelect }) {
  const tone = pipeline.computedTrust || pipeline.defaultTrust;
  return <button className={`pipeline-lane paper-panel ${tone}`} onClick={onSelect}>
    <div className="lane-meta"><StatusGlyph tone={tone} /><div><strong>{pipeline.name}</strong><span>{pipeline.env} · {pipeline.owner}</span></div><TrustBadge tone={tone} /></div>
    <div className="lane-path" aria-hidden="true"><span>{pipeline.source}</span><i /><span>{pipeline.context}</span><i /><span>{pipeline.agent}</span><i /><span className="tool-node">{pipeline.action}</span></div>
    <div className="lane-bottom"><span>{pipeline.change}</span><em>{pipeline.incidentId && tone !== "trusted" ? "Requires attention" : "No open block"}</em></div>
  </button>;
}

function PipelineDetail({ pipeline, openPipeline, openIncident, incidentStep, incidentResolved }) {
  const isRefund = pipeline.id === "refund";
  const trust = pipeline.computedTrust || pipeline.defaultTrust;
  return <section className="view detail-view" aria-labelledby="pipeline-heading">
    <Breadcrumb items={["Command Center", pipeline.name]} />
    <div className="detail-layout">
      <article className="paper-panel detail-main">
        <div className="detail-title"><div><p className="eyebrow">Selected pipeline</p><h1 id="pipeline-heading">{pipeline.name}</h1><p>{pipeline.version} · {pipeline.owner} · {pipeline.env}</p></div><TrustBadge tone={trust} /></div>
        <ContextAttestation pipeline={pipeline} trust={trust} incidentStep={incidentStep} incidentResolved={incidentResolved} />
        <h2>Smallest relevant context path</h2><Lineage step={isRefund ? incidentStep : 0} pipeline={pipeline} />
        <div className="split-blocks"><FactList title="DataHub supplied" items={pipeline.datahub} /><FactList title="Aegis decided" items={pipeline.aegis} /></div>
      </article>
      <aside className="paper-panel detail-aside"><h2>Operational impact</h2><dl className="definition-list"><div><dt>Highest-impact tool</dt><dd><code>{pipeline.actionDetail}</code></dd></div><div><dt>Current change</dt><dd>{pipeline.change}</dd></div><div><dt>Owner</dt><dd>{pipeline.owner}</dd></div></dl><h3>Recent context changes</h3><ul className="quiet-list">{pipeline.recent.map((item) => <li key={item}>{item}</li>)}</ul>{isRefund && !incidentResolved ? <button className="primary wide" onClick={openIncident}>Investigate incident</button> : <button className="secondary wide" onClick={() => openPipeline(pipeline.id)}>Refresh attestation</button>}</aside>
    </div>
  </section>;
}

function ContextAttestation({ pipeline, trust, incidentStep, incidentResolved }) {
  const state = pipeline.id === "refund" ? (incidentResolved ? "Trusted" : ["Trusted", "Invalidated", "Blocked", "Re-evaluated"][incidentStep]) : pipeline.defaultTrust === "review" ? "Review required" : "Trusted";
  return <section className={`attestation ${trust}`}><div><p className="eyebrow">Current Context Attestation</p><strong>{state}</strong><span>{pipeline.id === "refund" && !incidentResolved ? "Approval chain invalidated for monetary refund action." : "Context path matches approved governance state."}</span></div><div className="attestation-strip">{steps.map((step, index) => <span key={step} className={pipeline.id === "refund" && incidentStep >= index ? "lit" : ""}>{step}</span>)}</div></section>;
}

function IncidentWorkspace({ incidentStep, setIncidentStep, evidenceOpen, setEvidenceOpen, openPipeline, verifyRecovery, resetSimulation, incidentResolved }) {
  const blocked = incidentStep >= 2 && !incidentResolved;
  return <section className="view incident-view" aria-labelledby="incident-heading">
    <Breadcrumb items={["Command Center", "Refund Resolution Agent", INCIDENT_ID]} />
    <div className="incident-grid">
      <div className="incident-stack"><IncidentSummary incidentStep={incidentStep} setIncidentStep={setIncidentStep} evidenceOpen={evidenceOpen} setEvidenceOpen={setEvidenceOpen} openPipeline={openPipeline} verifyRecovery={verifyRecovery} incidentResolved={incidentResolved} /><Lineage step={incidentStep} pipeline={basePipelines[0]} /><TimelineControls incidentStep={incidentStep} setIncidentStep={setIncidentStep} resetSimulation={resetSimulation} /></div>
      {evidenceOpen || blocked ? <EvidencePanel open={evidenceOpen} setOpen={setEvidenceOpen} incidentStep={incidentStep} /> : <EvidenceClosed setOpen={setEvidenceOpen} />}
    </div>
  </section>;
}

function IncidentSummary({ incidentStep, setIncidentStep, evidenceOpen, setEvidenceOpen, openPipeline, verifyRecovery, incidentResolved }) {
  const tone = incidentResolved ? "trusted" : incidentStep >= 2 ? "blocked" : incidentStep === 1 ? "warning" : "trusted";
  const title = incidentResolved ? "Refund Resolution Agent is trusted again." : incidentStep >= 2 ? "Refund Resolution Agent blocked before issuing $8,500 refund." : incidentStep === 1 ? "Policy source changed; safety gate pending." : "Refund pipeline is healthy.";
  const body = incidentResolved ? "Aegis restored the approved refund policy, re-ran the control, and recorded resolution evidence to DataHub." : incidentStep >= 2 ? "An unapproved refund-policy document reached the RAG index. Aegis traced the DataHub path and blocked issue_refund before execution." : incidentStep === 1 ? "A simulated context change introduced refund-policy-q4-draft.md into the live context path." : "Start the simulation to see how context propagation changes the agent trust state.";
  return <article className={`summary paper-panel ${tone}`}><div className="summary-topline"><span>{INCIDENT_ID}</span><span>Production</span><span>ApprovedContextSource</span><TrustBadge tone={tone} /></div><h1 id="incident-heading">{title}</h1><p className="summary-subhead">{body}</p><div className="decision-grid"><Fact label="Causal change" value={incidentResolved ? "refund-policy-v12.md restored" : "refund-policy-q4-draft.md unapproved"} /><Fact label="Prevented action" value={incidentStep >= 2 && !incidentResolved ? "$8,500 refund blocked" : "issue_refund monitored"} /><Fact label="Control" value={incidentStep >= 2 && !incidentResolved ? "Failed · source not approved" : incidentResolved ? "Passed after remediation" : "Ready"} /><Fact label="Next step" value={incidentResolved ? "Return to Command Center" : incidentStep < 1 ? "Trigger simulated change" : incidentStep < 2 ? "Run safety gate" : "Investigate or remediate"} /></div><div className="summary-actions">{incidentStep < 1 && <button className="primary" onClick={() => setIncidentStep(1)}>Simulate context change</button>}{incidentStep === 1 && <button className="primary" onClick={() => setIncidentStep(2)}>Run safety gate</button>}{incidentStep >= 2 && !incidentResolved && <button className="primary" onClick={verifyRecovery}>Apply remediation</button>}<button className="secondary" onClick={() => setEvidenceOpen(!evidenceOpen)}>{evidenceOpen ? "Hide evidence" : "Investigate evidence"}</button><button className="ghost" onClick={openPipeline}>Open pipeline detail</button></div>{incidentResolved && <p className="resolution-note">Trusted state visible in Command Center.</p>}</article>;
}

function Lineage({ step, pipeline }) {
  const nodes = [{ type: "source", title: pipeline.source, meta: step > 0 && pipeline.id === "refund" ? "Approval: not approved" : "Approval: verified" }, { type: "context", title: pipeline.context, meta: "DataHub lineage edge" }, { type: "agent", title: pipeline.agent, meta: pipeline.version || "Production agent" }, { type: "tool", title: pipeline.action, meta: pipeline.id === "refund" && step >= 2 ? "$8,500 call blocked" : "Consequential tool" }];
  return <section className="lineage-wrap paper-panel" aria-label="DataHub lineage path"><div className="section-head"><p className="eyebrow">DataHub affected path</p><strong>source → retrieval → agent → tool</strong></div><div className="lineage">{nodes.map((node, index) => <React.Fragment key={node.type}><div className={`lineage-node ${step >= index ? "active" : ""}`}><span>{node.type}</span><strong>{node.title}</strong><em>{node.meta}</em></div>{index < nodes.length - 1 && <i className={`edge ${step > index ? "lit" : ""}`} />}</React.Fragment>)}</div></section>;
}

function EvidenceClosed({ setOpen }) { return <aside className="evidence-closed paper-panel"><p className="eyebrow">Evidence</p><strong>Evidence is available on request.</strong><span>Open investigation to inspect control results, provenance, and metadata.</span><button className="secondary" onClick={() => setOpen(true)}>Open evidence</button></aside>; }
function EvidencePanel({ open, setOpen, incidentStep }) { return <aside className="evidence-panel paper-panel" aria-label="Evidence panel"><div className="evidence-head"><div><p className="eyebrow">Investigation evidence</p><h2>Why Aegis blocked the refund</h2></div><button className="ghost" onClick={() => setOpen(!open)}>{open ? "Close" : "Collapse"}</button></div><EvidenceRow label="Failed control" value="ApprovedContextSource" detail="Production monetary tool call over $2,000 requires approved context source." /><EvidenceRow label="Tool call" value="issue_refund({ amount: 8500, currency: 'USD', case: 'CX-90214' })" detail="Intercepted before execution; downstream refund provider not called." /><EvidenceRow label="Source provenance" value="refund-policy-q4-draft.md · owner: Commerce Docs · approval: not approved" detail="DataHub change event dh-event-77b19 linked source to Refund RAG index." /><details><summary>Raw DataHub metadata and regression output</summary><pre>{JSON.stringify({ incident: INCIDENT_ID, step: steps[incidentStep], sourceUrn: "urn:li:document:refund-policy-q4-draft", approvedReplacement: "urn:li:document:refund-policy-v12", control: "ApprovedContextSource", regression: ["refund-cap-boundary: passed", "manual-review-threshold: passed", "negative-balance-case: passed"] }, null, 2)}</pre></details></aside>; }
function EvidenceRow({ label, value, detail }) { return <div className="evidence-row"><span>{label}</span><strong>{value}</strong><em>{detail}</em></div>; }
function TimelineControls({ incidentStep, setIncidentStep, resetSimulation }) { return <section className="timeline paper-panel" aria-label="Incident simulation controls"><div className="step-list">{steps.map((step, index) => <button key={step} className={`step-dot ${incidentStep === index ? "selected" : ""} ${incidentStep > index ? "done" : ""}`} onClick={() => setIncidentStep(index)}><span>{index + 1}</span><strong>{step}</strong></button>)}</div><button className="ghost" onClick={resetSimulation}>Reset simulation</button></section>; }
function ControlsView({ openIncident, incidentResolved }) { return <section className="view controls-view" aria-labelledby="controls-heading"><Breadcrumb items={["Command Center", "Controls", "ApprovedContextSource"]} /><article className="paper-panel control-card"><div className="detail-title"><div><p className="eyebrow">Deterministic safety control</p><h1 id="controls-heading">ApprovedContextSource</h1><p>Blocks consequential production tool calls when context approval is untrusted.</p></div><TrustBadge tone="trusted" label="Enabled" /></div><div className="rule-box"><strong>WHEN</strong><code>tool.risk = consequential AND tool.amount &gt; 2000</code><strong>REQUIRE</strong><code>context.source.approval = approved</code><strong>OTHERWISE</strong><code>block before tool execution</code></div><div className="control-grid"><Fact label="Coverage" value="Refund, account, claims tools" /><Fact label="Last result" value={incidentResolved ? "Passed after remediation" : "Failed for aegis-4821"} /><Fact label="Write-back" value="DataHub assertion + incident outcome" /><Fact label="Owner" value="AI Platform Safety" /></div><button className="primary" onClick={openIncident}>Open linked incident</button></article></section>; }
function FactList({ title, items }) { return <section className="fact-list"><h3>{title}</h3><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></section>; }
function Fact({ label, value }) { return <div className="fact"><span>{label}</span><strong>{value}</strong></div>; }
function Breadcrumb({ items }) { return <div className="breadcrumb">{items.map((item, index) => <React.Fragment key={item}><span>{item}</span>{index < items.length - 1 && <i>→</i>}</React.Fragment>)}</div>; }
function StatusGlyph({ tone }) { return <span className={`status-glyph ${tone || "trusted"}`} aria-hidden="true" />; }
function TrustBadge({ tone, label }) { const text = label || (tone === "blocked" ? "Blocked" : tone === "review" || tone === "warning" ? "Review" : "Trusted"); return <span className={`trust-badge ${tone}`}>{text}</span>; }

const styles = `
:root { --accent: var(--ocd-tweak-accent-color, ${TWEAK_DEFAULTS.accentColor}); --trust: var(--ocd-tweak-trust-color, ${TWEAK_DEFAULTS.trustColor}); --density: var(--ocd-tweak-density, ${TWEAK_DEFAULTS.density}); --motion: var(--ocd-tweak-motion-speed, ${TWEAK_DEFAULTS.motionSpeed}); --canvas: var(--ocd-tweak-canvas-max-width, ${TWEAK_DEFAULTS.canvasMaxWidth}); --bg: #ECE8DE; --surface: #FFFCF4; --paper: #F8F4EA; --ink: #1E241F; --muted: #687166; --line: #D8D0C2; --line-strong: #B9AF9F; --warning: #A36A1D; --shadow: 0 18px 55px rgba(49,42,31,.12); }
* { box-sizing: border-box; } body { margin: 0; background: var(--bg); color: var(--ink); font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; } button { font: inherit; color: inherit; } button:focus-visible, details:focus-within { outline: 3px solid color-mix(in oklab, var(--accent), white 45%); outline-offset: 3px; }
.aegis-app { min-height: 100vh; padding: calc(var(--density) * 18px); background: radial-gradient(circle at 18% -12%, rgba(182,58,47,.08), transparent 34%), linear-gradient(135deg, rgba(255,252,244,.5), rgba(236,232,222,.65)); }
.paper-panel { background: var(--surface); border: 1px solid var(--line); box-shadow: var(--shadow); }
.topbar, .view { width: min(var(--canvas), 100%); margin-inline: auto; }
.topbar { min-height: 72px; display: grid; grid-template-columns: auto 1fr auto; gap: 18px; align-items: center; padding: 12px 16px; position: sticky; top: 14px; z-index: 5; }
.brand { display: flex; gap: 12px; align-items: center; background: transparent; border: 0; cursor: pointer; text-align: left; } .brand-mark { width: 40px; height: 40px; display: grid; place-items: center; border: 1px solid var(--ink); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; font-weight: 800; } .brand strong, .brand em { display: block; } .brand em { color: var(--muted); font-size: 12px; font-style: normal; }
nav { display: flex; gap: 6px; justify-self: center; } nav button { background: transparent; border: 1px solid transparent; padding: 9px 11px; cursor: pointer; } nav button.active, nav button:hover { background: var(--paper); border-color: var(--line); }
.connection, .context-line, .summary-topline { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; color: var(--muted); font-size: 12px; } .connection code, code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: var(--ink); } .context-line { grid-column: 1 / -1; border-top: 1px solid var(--line); padding-top: 9px; }
.view { padding-top: calc(var(--density) * 22px); } .hero-row { display: grid; grid-template-columns: minmax(520px, 1fr) minmax(360px, 520px); gap: 18px; align-items: stretch; } .view-heading { max-width: 1080px; } .eyebrow { margin: 0 0 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: var(--muted); font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
h1 { margin: 0; max-width: 1120px; font-family: Georgia, "Times New Roman", serif; font-size: clamp(42px, 3.4vw, 70px); line-height: .96; letter-spacing: -.045em; } h2 { margin: 0 0 14px; font-size: 20px; } h3 { margin: 16px 0 10px; } p { line-height: 1.45; } .view-heading p:not(.eyebrow), .summary-subhead { color: var(--muted); font-size: 18px; max-width: 860px; }
.operator-note { display: grid; grid-template-columns: 1fr auto; gap: 10px 16px; align-content: center; padding: 18px; } .operator-note strong, .operator-note span { display: block; } .operator-note span { color: var(--muted); } .operator-note button { grid-row: 1 / span 2; grid-column: 2; }
.pipeline-lanes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 18px; } .pipeline-lane { min-height: 178px; padding: 16px; display: grid; gap: 15px; text-align: left; cursor: pointer; transition: transform calc(140ms * var(--motion)) ease, border-color calc(140ms * var(--motion)) ease; } .pipeline-lane:hover { transform: translateY(-2px); border-color: var(--ink); } .pipeline-lane.blocked { border-left: 5px solid var(--accent); } .pipeline-lane.review { border-left: 5px solid var(--warning); } .pipeline-lane.trusted { border-left: 5px solid var(--trust); }
.lane-meta, .lane-bottom, .detail-title, .section-head, .evidence-head { display: flex; justify-content: space-between; gap: 12px; align-items: start; } .lane-meta strong, .lane-meta span { display: block; } .lane-meta span, .lane-bottom, .quiet-list, .definition-list, .fact-list li { color: var(--muted); } .lane-bottom em { font-style: normal; font-weight: 800; color: var(--ink); }
.lane-path, .lineage { display: grid; grid-template-columns: 1fr 28px 1fr 28px 1fr 28px 1fr; gap: 8px; align-items: center; } .lane-path span, .lineage-node { border: 1px solid var(--line); background: var(--paper); padding: 10px; min-width: 0; } .lane-path .tool-node { border-color: var(--accent); } .lane-path i, .edge { height: 2px; background: var(--line-strong); position: relative; } .lane-path i:after, .edge:after { content: ""; position: absolute; right: 0; top: -4px; border-left: 7px solid var(--line-strong); border-top: 5px solid transparent; border-bottom: 5px solid transparent; }
.status-glyph { width: 11px; height: 11px; border-radius: 99px; background: var(--trust); box-shadow: 0 0 0 4px rgba(25,113,91,.13); flex: 0 0 auto; } .status-glyph.blocked { background: var(--accent); box-shadow: 0 0 0 4px rgba(182,58,47,.14); } .status-glyph.review { background: var(--warning); box-shadow: 0 0 0 4px rgba(163,106,29,.14); }
.trust-badge { border: 1px solid currentColor; padding: 5px 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; text-transform: uppercase; color: var(--trust); white-space: nowrap; } .trust-badge.blocked { color: var(--accent); } .trust-badge.review, .trust-badge.warning { color: var(--warning); }
.breadcrumb { display: flex; gap: 8px; align-items: center; color: var(--muted); font-size: 13px; margin-bottom: 14px; } .detail-layout, .incident-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(380px, 480px); gap: 18px; } .detail-main, .detail-aside, .summary, .lineage-wrap, .timeline, .evidence-panel, .evidence-closed, .control-card { padding: calc(var(--density) * 20px); }
.attestation { display: grid; grid-template-columns: minmax(220px, .45fr) 1fr; gap: 20px; padding: 16px; background: var(--paper); border: 1px solid var(--line); margin: 18px 0; } .attestation strong { display: block; font-size: 26px; } .attestation span { color: var(--muted); } .attestation-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; align-content: center; } .attestation-strip span { border-top: 3px solid var(--line); padding-top: 8px; font-size: 12px; } .attestation-strip .lit { border-color: var(--trust); color: var(--ink); } .attestation.blocked .attestation-strip .lit:nth-child(3) { border-color: var(--accent); }
.split-blocks, .control-grid, .decision-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; } .decision-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 20px 0; } .fact { border-top: 2px solid var(--line-strong); padding-top: 10px; min-width: 0; } .fact span { display: block; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; } .fact strong { display: block; margin-top: 5px; line-height: 1.25; } .fact-list { background: var(--paper); border: 1px solid var(--line); padding: 14px; } .fact-list ul, .quiet-list { margin: 0; padding-left: 18px; }
.summary { border-left: 5px solid var(--trust); } .summary.blocked { border-left-color: var(--accent); } .summary.warning { border-left-color: var(--warning); } .summary-actions { display: flex; flex-wrap: wrap; gap: 10px; } .resolution-note { margin: 14px 0 0; color: var(--trust); font-weight: 800; }
.primary, .secondary, .ghost { border: 1px solid var(--ink); padding: 11px 14px; cursor: pointer; transition: transform calc(140ms * var(--motion)) ease, background calc(140ms * var(--motion)) ease; } .primary { background: var(--ink); color: var(--surface); } .secondary { background: var(--surface); color: var(--ink); } .ghost { background: transparent; color: var(--muted); border-color: var(--line-strong); } .primary:hover, .secondary:hover, .ghost:hover { transform: translateY(-1px); } .wide { width: 100%; margin-top: 16px; }
.incident-stack { display: grid; gap: 14px; } .lineage-node { min-height: 104px; transition: border-color calc(180ms * var(--motion)) ease, transform calc(180ms * var(--motion)) ease; } .lineage-node.active { border-color: var(--ink); transform: translateY(-1px); } .lineage-node span { display: block; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; } .lineage-node strong { display: block; margin: 10px 0; } .lineage-node em { color: var(--muted); font-style: normal; font-size: 12px; } .edge.lit { background: var(--accent); animation: flow calc(.6s * var(--motion)) ease both; } .edge.lit:after { border-left-color: var(--accent); }
.evidence-closed { min-height: 245px; display: grid; gap: 10px; align-content: start; } .evidence-closed span { color: var(--muted); } .evidence-panel { position: sticky; top: 112px; max-height: calc(100vh - 132px); overflow: auto; } .evidence-row { border: 1px solid var(--line); background: var(--paper); padding: 14px; margin-bottom: 10px; } .evidence-row span { display: block; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; } .evidence-row strong { display: block; line-height: 1.28; word-break: break-word; } .evidence-row em { display: block; margin-top: 8px; color: var(--muted); font-style: normal; font-size: 13px; } details { border: 1px solid var(--line); background: #252923; color: var(--surface); padding: 12px; } summary { cursor: pointer; font-weight: 800; } pre { white-space: pre-wrap; font-size: 12px; line-height: 1.5; color: #D9E0D6; }
.timeline { display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center; box-shadow: none; } .step-list { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; } .step-dot { min-height: 48px; border: 1px solid var(--line); background: var(--paper); text-align: left; padding: 8px; display: flex; gap: 9px; align-items: center; cursor: pointer; color: var(--muted); } .step-dot span { width: 26px; height: 26px; border: 1px solid currentColor; border-radius: 99px; display: grid; place-items: center; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; } .step-dot.selected { color: var(--ink); border-color: var(--ink); background: var(--surface); } .step-dot.done span { background: var(--trust); color: white; border-color: var(--trust); }
.control-card { max-width: min(var(--canvas), 1280px); } .rule-box { display: grid; grid-template-columns: auto 1fr; gap: 8px 14px; padding: 16px; border: 1px solid var(--line); background: var(--paper); margin: 18px 0; } .rule-box code { color: var(--accent); font-weight: 800; }
@keyframes flow { from { transform: scaleX(.15); transform-origin: left; opacity: .35; } to { transform: scaleX(1); opacity: 1; } }
@media (min-width: 1600px) { .aegis-app { padding: calc(var(--density) * 24px); } .topbar { grid-template-columns: auto 1fr minmax(500px, auto); } .context-line { grid-column: auto; border-top: 0; padding-top: 0; justify-content: end; } .hero-row { grid-template-columns: minmax(760px, 1fr) minmax(430px, 560px); } .pipeline-lanes { grid-template-columns: repeat(4, minmax(0, 1fr)); } .pipeline-lane { min-height: 300px; align-content: space-between; } .lane-path { grid-template-columns: 1fr; } .lane-path i { width: 2px; height: 18px; justify-self: center; } .lane-path i:after { top: auto; bottom: 0; right: -4px; transform: rotate(90deg); } .detail-layout, .incident-grid { grid-template-columns: minmax(0, 1fr) minmax(460px, 540px); } .lineage-node { min-height: 120px; } }
@media (max-width: 1100px) { .topbar { grid-template-columns: 1fr; position: static; } nav { justify-self: stretch; overflow-x: auto; } .connection { white-space: normal; } .hero-row, .detail-layout, .incident-grid { grid-template-columns: 1fr; } .evidence-panel { position: static; max-height: none; } .lane-path, .lineage { grid-template-columns: 1fr; } .lane-path i, .edge { width: 2px; height: 18px; justify-self: center; } .lane-path i:after, .edge:after { top: auto; bottom: 0; right: -4px; transform: rotate(90deg); } .decision-grid, .control-grid, .split-blocks, .pipeline-lanes { grid-template-columns: 1fr 1fr; } }
@media (max-width: 720px) { .aegis-app { padding: 14px; } h1 { font-size: 38px; } .operator-note, .attestation, .timeline { grid-template-columns: 1fr; } .decision-grid, .control-grid, .split-blocks, .step-list, .pipeline-lanes { grid-template-columns: 1fr; } .lane-bottom, .detail-title, .section-head, .evidence-head { flex-direction: column; align-items: start; } }
@media (prefers-reduced-motion: reduce) { *, *:before, *:after { animation: none !important; transition: none !important; scroll-behavior: auto !important; } }
`;

const aegisTypographyRepairId = 'aegis-typography-spacing-repair';
if (typeof document !== 'undefined' && !document.getElementById(aegisTypographyRepairId)) {
  const typographyRepairStyle = document.createElement('style');
  typographyRepairStyle.id = aegisTypographyRepairId;
  typographyRepairStyle.textContent = `
    :root {
      --ocd-tweak-heading-tracking: -0.015em;
      --ocd-tweak-heading-line-height: 1.04;
      --ocd-tweak-body-line-height: 1.52;
    }

    .app-shell h1,
    .app-shell h2,
    .app-shell .hero-title,
    .app-shell .page-title,
    .app-shell .incident-title,
    .app-shell [style*="Source Serif"] {
      letter-spacing: var(--ocd-tweak-heading-tracking) !important;
      word-spacing: 0.045em !important;
      line-height: var(--ocd-tweak-heading-line-height) !important;
      text-wrap: balance;
      font-kerning: normal;
      font-feature-settings: "kern" 1, "liga" 1;
    }

    .app-shell h1,
    .app-shell .hero-title,
    .app-shell .page-title {
      max-width: 19ch;
      padding-bottom: 0.055em;
    }

    .app-shell h2,
    .app-shell h3,
    .app-shell .section-title,
    .app-shell .control-title,
    .app-shell .pipeline-title {
      overflow-wrap: anywhere;
      line-height: 1.12 !important;
    }

    .app-shell p,
    .app-shell li,
    .app-shell .lede,
    .app-shell .subtitle,
    .app-shell .description,
    .app-shell .body-copy {
      line-height: var(--ocd-tweak-body-line-height) !important;
      word-spacing: 0.018em;
    }

    .app-shell .mono,
    .app-shell code,
    .app-shell [style*="IBM Plex Mono"],
    .app-shell [class*="meta"],
    .app-shell [class*="hash"] {
      letter-spacing: 0.015em !important;
      line-height: 1.45 !important;
      overflow-wrap: anywhere;
    }

    .app-shell [class*="lineage"] *,
    .app-shell [class*="path"] *,
    .app-shell [class*="node"] *,
    .app-shell [class*="tool"] *,
    .app-shell [class*="lane"] * {
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
      white-space: normal;
    }

    .app-shell [class*="lineage"] [style*="border"],
    .app-shell [class*="path"] [style*="border"],
    .app-shell [class*="lane"] [style*="border"] {
      line-height: 1.14 !important;
      padding-inline: 10px !important;
    }

    .app-shell [class*="lineage"] code,
    .app-shell [class*="path"] code,
    .app-shell [class*="node"] code,
    .app-shell [class*="tool"] code {
      line-height: 1.25 !important;
    }

    @media (min-width: 1600px) {
      .app-shell h1,
      .app-shell .hero-title,
      .app-shell .page-title {
        max-width: 22ch;
      }
    }
  `;
  document.head.appendChild(typographyRepairStyle);
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
