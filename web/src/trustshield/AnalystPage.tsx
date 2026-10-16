import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, fmtINR } from "../shared/api";
import { Badge, Card, Gauge, Md, Spinner } from "../shared/ui";
import Graph from "./Graph";
import SignalBars from "./SignalBars";

function Highlighted({ text, quotes }: { text: string; quotes: string[] }) {
  const ranges: [number, number][] = [];
  const lower = text.toLowerCase();
  for (const q of quotes) {
    const i = lower.indexOf(q.toLowerCase().trim());
    if (i >= 0 && q.trim()) ranges.push([i, i + q.trim().length]);
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const parts: JSX.Element[] = [];
  let pos = 0;
  ranges.forEach(([s, e], k) => {
    if (s < pos) return;
    parts.push(<span key={`t${k}`}>{text.slice(pos, s)}</span>);
    parts.push(<mark key={`m${k}`}>{text.slice(s, e)}</mark>);
    pos = e;
  });
  parts.push(<span key="end">{text.slice(pos)}</span>);
  return <div className="transcript">{parts}</div>;
}

function Detail({ id }: { id: string }) {
  const [d, setD] = useState<any>(null);
  const [graph, setGraph] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [resolved, setResolved] = useState<any>(null);
  useEffect(() => {
    setD(null); setGraph(null); setSummary(null); setResolved(null);
    api(`/api/ts/assessments/${id}/detail`).then((x) => {
      setD(x);
      if (x.assessment.matched_campaigns[0]) api(`/api/ts/campaigns/${x.assessment.matched_campaigns[0]}/summary`).then(setSummary);
    });
    api(`/api/ts/graph/assessment/${id}`).then(setGraph);
  }, [id]);
  if (!d) return <Card><Spinner /></Card>;
  const a = d.assessment;
  const resolve = async (verdict: string) => setResolved(await api(`/api/ts/cases/${d.case.case_id}/resolve`, { json: { verdict, notes: "" } }));
  return (
    <div className="col" style={{ gap: 16 }}>
      <Card title={<>{a.customer_name} → {a.beneficiary.display_name} <Badge tone={a.final_decision}>{a.final_decision}</Badge></>}
        extra={<small className="mono">{a.assessment_id}</small>}>
        <div className="grid g4" style={{ marginBottom: 12 }}>
          <div className="stat"><span className="v">{a.amount_fmt}</span><span className="l">amount · note "{a.note}"</span></div>
          <div className="stat"><span className="v">{(a.risk * 100).toFixed(1)}%</span><span className="l">fused risk {a.hard_rule ? `· hard rule ${a.hard_rule}` : ""}</span></div>
          <div className="stat"><span className="v">{a.latency_ms.total} ms</span><span className="l">end-to-end latency</span></div>
          <div className="stat"><span className="v" style={{ fontSize: 14 }}>{a.meta.analyzer}</span><span className="l">{a.meta.explainer} · {a.meta.policy_version}</span></div>
        </div>
        <div className="grid g4">
          <Gauge label="Behaviour" value={a.scores.behaviour} color="var(--info)" />
          <Gauge label="Scam content" value={a.scores.content} color="var(--hold)" />
          <Gauge label="Network intel" value={a.scores.intel} color="#ae3ec9" />
          <Gauge label="Legit context" value={a.scores.legit} color="var(--pass)" />
        </div>
        {a.counterfactual && (
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
            <div className="row between">
              <b>Decision replay</b>
              <small>Same policy, transaction signals only vs full context</small>
            </div>
            <div className="grid g3" style={{ marginTop: 10 }}>
              <div className="stat">
                <span className="v">{(a.counterfactual.behaviour_only.risk * 100).toFixed(1)}%</span>
                <span className="l">Behavior only · <Badge tone={a.counterfactual.behaviour_only.decision}>{a.counterfactual.behaviour_only.decision}</Badge></span>
              </div>
              <div className="stat">
                <span className="v">{(a.counterfactual.full_context.risk * 100).toFixed(1)}%</span>
                <span className="l">Full context · <Badge tone={a.counterfactual.full_context.decision}>{a.counterfactual.full_context.decision}</Badge></span>
              </div>
              <div className="stat">
                <span className="v">{a.counterfactual.risk_delta >= 0 ? "+" : ""}{(a.counterfactual.risk_delta * 100).toFixed(1)} pp</span>
                <span className="l">Risk change after content and intelligence</span>
              </div>
            </div>
            <small className="muted">A deterministic counterfactual for this synthetic assessment, not proof of production accuracy.</small>
          </div>
        )}
        {d.case && (
          <div className="row" style={{ marginTop: 14 }}>
            <Badge tone={d.case.status === "open" ? "warning" : d.case.status === "released" ? "ok" : "bad"}>case {d.case.status}</Badge>
            {d.case.status === "open" && !resolved && (
              <>
                <button className="danger" onClick={() => resolve("confirmed_scam")}>Confirm scam (learn indicators)</button>
                <button onClick={() => resolve("released")}>Release payment</button>
              </>
            )}
            {resolved && <small>Resolved as <b>{resolved.status}</b>. New indicators learned: {resolved.learned_indicators.length ? resolved.learned_indicators.join(", ") : "none (already known)"}</small>}
            {a.safety_flags?.length > 0 && <Badge tone="bad">escalated by safety answers</Badge>}
          </div>
        )}
      </Card>
      <div className="grid g2">
        <Card title="Evidence">
          {d.evidence.length === 0 && <div className="empty">No evidence attached. Behaviour + intel only.</div>}
          {d.evidence.filter((e: any) => e.url).map((e: any) => <img key={e.evidence_id} className="evidence-img" src={e.url} alt="evidence" />)}
          {a.analysis && (
            <div className="col" style={{ marginTop: 10 }}>
              <div className="row"><b>{a.analysis.scam_type.replace(/_/g, " ")}</b>
                <Badge>{Math.round(a.analysis.confidence * 100)}% conf.</Badge>
                {a.analysis.impersonated_org && <Badge tone="bad">impersonates {a.analysis.impersonated_org}</Badge>}
                {a.analysis.quote_accuracy !== null && <Badge tone={a.analysis.quote_accuracy === 1 ? "ok" : "warning"}>quotes verified {Math.round(a.analysis.quote_accuracy * 100)}%</Badge>}
              </div>
              <small>{a.analysis.summary}</small>
              <h4>Transcript (PII-redacted) with tactic quotes</h4>
              <Highlighted text={a.analysis.transcript_redacted} quotes={a.analysis.tactics.map((t: any) => t.quote)} />
              <div className="row">{a.analysis.tactics.map((t: any, i: number) => <Badge key={i} tone="bad">{t.name} {Math.round(t.severity * 100)}</Badge>)}</div>
            </div>
          )}
        </Card>
        <Card title="Why: signal contributions">
          <SignalBars signals={a.signals} max={12} />
          <h4 style={{ marginTop: 14 }}>Customer intervention ({a.language})</h4>
          <p style={{ margin: 0 }}><b>{a.intervention.headline}</b></p>
          <p style={{ marginTop: 4 }}>{a.intervention.customer_message}</p>
          <small>{a.intervention.analyst_rationale}</small>
        </Card>
      </div>
      <div className="grid g2">
        <Card title="Scam network" extra={graph && <small>{graph.nodes.length} nodes · {graph.campaigns.join(", ") || "no campaign link"}</small>}>
          {graph ? <Graph data={graph} /> : <Spinner />}
        </Card>
        <Card title="Campaign summary" extra={summary && <small>{summary.generated_by}</small>}>
          {!a.matched_campaigns.length && <div className="empty">No known campaign matched.</div>}
          {summary && (
            <div className="col">
              <b>{summary.title}</b>
              <p style={{ margin: 0 }}>{summary.narrative}</p>
              <h4>Modus operandi</h4>
              <Md text={summary.modus_operandi.map((x: string) => `- ${x}`).join("\n")} />
              <h4>Recommended actions</h4>
              <Md text={summary.recommended_actions.map((x: string) => `- ${x}`).join("\n")} />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export default function AnalystPage() {
  const { caseId } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const [cases, setCases] = useState<any[]>([]);
  const [recent, setRecent] = useState<any[]>([]);
  const [sel, setSel] = useState<string | null>(sp.get("assessment"));
  useEffect(() => {
    api("/api/ts/cases").then((cs) => {
      setCases(cs);
      if (caseId) setSel(cs.find((c: any) => c.case_id === caseId)?.assessment_id ?? null);
      else if (!sp.get("assessment") && cs[0]) setSel(cs[0].assessment_id);
    });
    api("/api/ts/assessments?limit=30").then(setRecent);
  }, [caseId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="page split-l">
      <div className="col" style={{ gap: 16 }}>
        <Card title="Case queue" extra={<Badge tone="warning">{cases.filter((c) => c.status === "open").length} open</Badge>}>
          {cases.length === 0 && <div className="empty">No HOLD cases yet. Make a scam payment in the Pay screen.</div>}
          <table><tbody>
            {cases.map((c) => (
              <tr key={c.case_id} className={`click ${sel === c.assessment_id ? "sel" : ""}`} onClick={() => { setSel(c.assessment_id); nav("/ts/analyst"); }}>
                <td><b>{c.customer_name}</b><br /><small>{(c.scam_type ?? "no evidence").replace(/_/g, " ")} · {c.reason}</small></td>
                <td className="num">{fmtINR(c.amount)}<br /><Badge tone={c.status === "open" ? "warning" : c.status === "released" ? "ok" : "bad"}>{c.status}</Badge></td>
              </tr>
            ))}
          </tbody></table>
        </Card>
        <Card title="All recent assessments">
          <table><tbody>
            {recent.map((a) => (
              <tr key={a.assessment_id} className={`click ${sel === a.assessment_id ? "sel" : ""}`} onClick={() => setSel(a.assessment_id)}>
                <td>{a.customer_name}<br /><small>{a.beneficiary.display_name}</small></td>
                <td className="num">{a.amount_fmt}<br /><Badge tone={a.final_decision}>{a.final_decision}</Badge></td>
              </tr>
            ))}
          </tbody></table>
        </Card>
      </div>
      {sel ? <Detail id={sel} /> : <Card><div className="empty">Select a case.</div></Card>}
    </div>
  );
}
