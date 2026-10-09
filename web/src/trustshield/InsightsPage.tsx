import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, pct } from "../shared/api";
import { Badge, Card, ErrorLine, Spinner, Stat } from "../shared/ui";

const CFG_LABEL: Record<string, string> = {
  behaviour_only: "Behaviour only", "behaviour+intel": "+ Network intel", "behaviour+content": "+ Gemini content", full: "Full TrustShield",
};

export default function InsightsPage() {
  const [ins, setIns] = useState<any>(null);
  const [run, setRun] = useState<any>(null);
  const [calls, setCalls] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [n, setN] = useState(400);
  const [live, setLive] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = () => {
    api("/api/ts/insights").then(setIns);
    api("/api/ts/eval/latest").then(setRun);
    api("/api/system/gemini-calls?n=15").then(setCalls);
  };
  useEffect(load, []);

  const runEval = async () => {
    setBusy(true); setErr(null);
    try { setRun(await api(`/api/ts/eval/run?n=${n}&live=${live}`, { method: "POST" })); load(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const chart = run ? Object.entries(run.results).map(([k, v]: any) => ({
    name: CFG_LABEL[k] ?? k, Recall: v.recall, Precision: v.precision, "False-positive rate": v.fpr, "Value intercepted": v.value_intercepted_pct,
  })) : [];

  return (
    <div className="page col" style={{ gap: 16 }}>
      <Card title="Live operations" extra={<span className="synthetic">SYNTHETIC</span>}>
        {ins ? (
          <div className="grid g5">
            <Stat label="Assessments" value={ins.assessments} />
            <Stat label="PASS / WARN / HOLD" value={`${ins.decisions.PASS} / ${ins.decisions.WARN} / ${ins.decisions.HOLD}`} />
            <Stat label="Value protected (held or cancelled)" value={ins.value_protected_fmt} tone="pass" />
            <Stat label="Latency p50 / p95" value={ins.latency_p50 ? `${ins.latency_p50} / ${ins.latency_p95} ms` : "–"} />
            <Stat label="Open cases · campaigns" value={`${ins.open_cases} · ${ins.campaigns}`} />
          </div>
        ) : <Spinner />}
      </Card>

      <Card title="Benchmark & ablation: does Gemini add value?"
        extra={<div className="row">
          <label className="check"><input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} /> use Gemini if available</label>
          <select value={n} onChange={(e) => setN(Number(e.target.value))} style={{ width: 110 }}>
            {[100, 200, 400, 800].map((x) => <option key={x} value={x}>{x} cases</option>)}
          </select>
          <button className="primary" onClick={runEval} disabled={busy}>{busy ? <><Spinner /> Running…</> : "Run benchmark"}</button>
        </div>}>
        <ErrorLine error={err} />
        {!run ? <div className="empty">No run yet. Click "Run benchmark".</div> : (
          <div className="col" style={{ gap: 14 }}>
            <div className="row">
              <Badge tone="brand">content analyser: {run.content_analyzer}</Badge>
              <Badge>{run.n} payments · {run.n_scam} scams · {run.n_legit} legit</Badge>
              <Badge>quote accuracy {pct(run.quote_accuracy)}</Badge>
              <Badge tone={run.injection_robustness === 1 ? "ok" : "warning"}>prompt-injection robustness {pct(run.injection_robustness)}</Badge>
              {run.analysis_latency_ms_p50 !== null && <Badge>analysis p50/p95 {run.analysis_latency_ms_p50}/{run.analysis_latency_ms_p95} ms</Badge>}
            </div>
            <div style={{ height: 300 }}>
              <ResponsiveContainer>
                <BarChart data={chart} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--muted)" }} />
                  <YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fontSize: 12, fill: "var(--muted)" }} />
                  <Tooltip formatter={(v: any) => pct(v, 1)} contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }} />
                  <Legend />
                  <Bar dataKey="Recall" fill="#3b5bdb" />
                  <Bar dataKey="Precision" fill="#0ca678" />
                  <Bar dataKey="False-positive rate" fill="#d6336c" />
                  <Bar dataKey="Value intercepted" fill="#e8890c" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <table>
              <thead><tr><th>Configuration</th><th className="num">Recall</th><th className="num">Precision</th><th className="num">FPR</th>
                <th className="num">HOLD-FPR</th><th className="num">HOLD recall</th><th className="num">Value intercepted</th><th className="num">WARN/HOLD</th></tr></thead>
              <tbody>{Object.entries(run.results).map(([k, v]: any) => (
                <tr key={k}><td><b>{CFG_LABEL[k] ?? k}</b></td><td className="num">{pct(v.recall)}</td><td className="num">{pct(v.precision)}</td>
                  <td className="num">{pct(v.fpr, 1)}</td><td className="num">{pct(v.hold_fpr, 1)}</td><td className="num">{pct(v.hold_recall)}</td>
                  <td className="num">{pct(v.value_intercepted_pct)}</td><td className="num">{v.warn}/{v.hold}</td></tr>
              ))}</tbody>
            </table>
            <details>
              <summary>Per scenario type (flagged by behaviour-only vs full)</summary>
              <table><thead><tr><th>Type</th><th className="num">n</th><th className="num">Behaviour only</th><th className="num">Full</th></tr></thead>
                <tbody>{Object.entries(run.by_kind).sort().map(([k, v]: any) => (
                  <tr key={k}><td>{k}</td><td className="num">{v.n}</td><td className="num">{v.flagged_behaviour}</td><td className="num">{v.flagged_full}</td></tr>
                ))}</tbody></table>
            </details>
            <small className="muted">{run.note} Run {run.run_id} · {run.created_at}</small>
          </div>
        )}
      </Card>

      <div className="grid g2">
        <Card title="Event stream (Pub/Sub → BigQuery)">
          <div className="scroll" style={{ maxHeight: 320 }}>
            <table><tbody>{(ins?.events ?? []).map((e: any, i: number) => (
              <tr key={i}><td><Badge tone="brand">{e.event}</Badge></td><td className="mono">{JSON.stringify(e.payload).slice(0, 110)}…</td></tr>
            ))}</tbody></table>
          </div>
        </Card>
        <Card title="Recent Gemini calls">
          {calls.length === 0 ? <div className="empty">No live Gemini calls (offline mock mode).</div> : (
            <table><thead><tr><th>Purpose</th><th>Model</th><th className="num">ms</th><th className="num">tokens in/out</th></tr></thead>
              <tbody>{calls.map((c, i) => (
                <tr key={i}><td>{c.purpose} {!c.ok && <Badge tone="bad">error</Badge>}</td><td className="mono">{c.model}</td>
                  <td className="num">{c.latency_ms}</td><td className="num">{c.in_tokens ?? "–"}/{c.out_tokens ?? "–"}</td></tr>
              ))}</tbody></table>
          )}
        </Card>
      </div>
    </div>
  );
}
