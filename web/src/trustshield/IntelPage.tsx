import { useEffect, useState } from "react";
import { api } from "../shared/api";
import { Badge, Card, ErrorLine, Md, Spinner } from "../shared/ui";
import Graph from "./Graph";

export default function IntelPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [indicators, setIndicators] = useState<any[]>([]);
  const [sel, setSel] = useState<string>("C-17");
  const [graph, setGraph] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [share, setShare] = useState({ kind: "phone", value: "+91 70123 45690", campaign_hint: "", confidence: 0.85 });
  const [shared, setShared] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = () => {
    api("/api/ts/campaigns").then(setCampaigns);
    api("/api/ts/indicators").then(setIndicators);
  };
  useEffect(load, []);
  useEffect(() => {
    setGraph(null); setSummary(null);
    api(`/api/ts/graph/campaign/${sel}`).then(setGraph);
    api(`/api/ts/campaigns/${sel}/summary`).then(setSummary);
  }, [sel]);

  const doShare = async () => {
    setErr(null);
    try {
      setShared(await api("/api/ts/intel/bank-b/share", { json: { ...share, campaign_hint: share.campaign_hint || null } }));
      load();
    } catch (e: any) { setErr(e.message); }
  };

  return (
    <div className="page col" style={{ gap: 16 }}>
      <div className="grid g2">
        <Card title="Active scam campaigns">
          <table>
            <thead><tr><th>Campaign</th><th>Type</th><th className="num">Indicators</th><th className="num">Victims</th><th>Banks</th></tr></thead>
            <tbody>
              {campaigns.map((c) => (
                <tr key={c.campaign_id} className={`click ${sel === c.campaign_id ? "sel" : ""}`} onClick={() => setSel(c.campaign_id)}>
                  <td><b>{c.campaign_id}</b> {c.label}</td><td>{c.scam_type.replace(/_/g, " ")}</td>
                  <td className="num">{c.indicator_hashes.length}</td><td className="num">{c.victim_count}</td>
                  <td>{c.banks_reporting.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {summary && (
            <div className="col" style={{ marginTop: 14 }}>
              <div className="row between"><b>{summary.title}</b><small>{summary.generated_by}</small></div>
              <p style={{ margin: 0 }}>{summary.narrative}</p>
              <Md text={summary.recommended_actions.map((x: string) => `- ${x}`).join("\n")} />
            </div>
          )}
        </Card>
        <Card title={`Campaign graph · ${sel}`}>{graph ? <Graph data={graph} /> : <Spinner />}</Card>
      </div>
      <div className="grid g2">
        <Card title="Privacy-preserving intel exchange (Bank B → consortium)">
          <p className="muted" style={{ marginTop: 0 }}>Bank B's node normalises and <b>HMAC-hashes</b> the indicator locally.
            Only the hash and metadata cross the boundary; no customer data or raw messages are shared.</p>
          <div className="grid g2">
            <label>Indicator type
              <select value={share.kind} onChange={(e) => setShare({ ...share, kind: e.target.value })}>
                <option value="phone">phone</option><option value="url_domain">url domain</option>
                <option value="account">account</option><option value="upi">upi</option>
              </select>
            </label>
            <label>Value (stays inside Bank B)<input value={share.value} onChange={(e) => setShare({ ...share, value: e.target.value })} /></label>
            <label>Campaign hint (optional)<input value={share.campaign_hint} onChange={(e) => setShare({ ...share, campaign_hint: e.target.value })} placeholder="e.g. C-17" /></label>
            <label>Confidence<input type="number" step="0.05" min="0" max="1" value={share.confidence} onChange={(e) => setShare({ ...share, confidence: Number(e.target.value) })} /></label>
          </div>
          <div className="row" style={{ marginTop: 10 }}><button className="primary" onClick={doShare}>Share hashed indicator</button><ErrorLine error={err} /></div>
          {shared && (
            <div className="col" style={{ marginTop: 10 }}>
              <h4>Payload actually transmitted</h4>
              <pre className="transcript mono">{JSON.stringify(shared.transmitted_payload, null, 2)}</pre>
              <Badge tone="brand">{shared.receipt.status}</Badge>
            </div>
          )}
        </Card>
        <Card title="Indicator watchlist (hashed)" extra={<small>{indicators.length} indicators</small>}>
          <div className="scroll" style={{ maxHeight: 420 }}>
            <table>
              <thead><tr><th>Indicator</th><th>Hash</th><th>Campaign</th><th className="num">Conf.</th><th>Reported by</th></tr></thead>
              <tbody>
                {indicators.map((i) => (
                  <tr key={i.hash}>
                    <td>{i.display}<br /><small>{i.kind}</small></td><td className="mono">{i.hash.slice(0, 10)}…</td>
                    <td>{i.campaign_id}</td><td className="num">{i.confidence}</td><td>{i.banks_reporting.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
