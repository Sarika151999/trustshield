import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtINR, form } from "../shared/api";
import { Badge, Card, ErrorLine, Gauge, Spinner } from "../shared/ui";
import DecisionModal from "./DecisionModal";
import SignalBars from "./SignalBars";

type Ben = { ben_id: string; display_name: string; account_masked: string; added_at: string; prior_payment_count: number };
type Customer = { customer_id: string; name: string; language: string; vulnerable: boolean; age_band: string;
  stats: { balance: number; mean_90d: number }; beneficiaries: Ben[] };
type Sample = { id: string; title: string; channel: string; label: string; image_url: string };

export default function PayPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [suggested, setSuggested] = useState<any[]>([]);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [cid, setCid] = useState("c_priya");
  const [benId, setBenId] = useState<string>("");
  const [amount, setAmount] = useState("85000");
  const [note, setNote] = useState("KYC verification deposit");
  const [onCall, setOnCall] = useState(false);
  const [newDevice, setNewDevice] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [pasted, setPasted] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [adding, setAdding] = useState(false);
  const [newPayee, setNewPayee] = useState({ display_name: "", account: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [showModal, setShowModal] = useState(false);

  const load = async () => {
    const r = await api("/api/ts/customers");
    setCustomers(r.customers);
    setSuggested(r.suggested_payees);
  };
  useEffect(() => {
    load();
    api<Sample[]>("/api/ts/samples").then(setSamples);
  }, []);
  const cust = useMemo(() => customers.find((c) => c.customer_id === cid), [customers, cid]);
  useEffect(() => {
    if (cust && !cust.beneficiaries.some((b) => b.ben_id === benId)) setBenId(cust.beneficiaries[0]?.ben_id ?? "");
  }, [cust]); // eslint-disable-line react-hooks/exhaustive-deps

  const addPayee = async (p: { display_name: string; account: string; bank_code?: string }) => {
    const b = await api("/api/ts/beneficiaries", { json: { customer_id: cid, ...p } });
    await load();
    setBenId(b.ben_id);
    setAdding(false);
    setNewPayee({ display_name: "", account: "" });
  };

  const pay = async () => {
    setBusy(true);
    setErr(null);
    try {
      const ids: string[] = [];
      for (const sid of picked) {
        ids.push((await api("/api/ts/evidence/sample", { form: form({ customer_id: cid, sample_id: sid }) })).evidence_id);
      }
      if (pasted.trim()) ids.push((await api("/api/ts/evidence/text", { form: form({ customer_id: cid, text: pasted }) })).evidence_id);
      if (file) ids.push((await api("/api/ts/evidence/upload", { form: form({ customer_id: cid, file }) })).evidence_id);
      const r = await api("/api/ts/assess", {
        json: { customer_id: cid, ben_id: benId, amount: Number(amount), note, context: { active_call: onCall, new_device: newDevice }, evidence_ids: ids },
      });
      setResult(r);
      setShowModal(true);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const ago = (iso: string) => {
    const m = (Date.now() - new Date(iso).getTime()) / 60000;
    return m < 60 ? `added ${Math.max(1, Math.round(m))} min ago` : m < 1440 ? `added ${Math.round(m / 60)} h ago` : "";
  };

  return (
    <div className="page split">
      <div className="phone">
        <div className="appbar">
          <div className="row between">
            <b>TrustBank</b>
            <select value={cid} onChange={(e) => setCid(e.target.value)} style={{ width: "auto", padding: "2px 6px", fontSize: 12 }}>
              {customers.map((c) => <option key={c.customer_id} value={c.customer_id}>{c.name}{c.vulnerable ? " (vulnerable)" : ""}</option>)}
            </select>
          </div>
          <small style={{ color: "#dfe4ff" }}>Available balance</small>
          <div className="bal">{fmtINR(cust?.stats.balance)}</div>
        </div>
        <div className="body">
          <div className="row between"><h3 style={{ margin: 0 }}>Pay to</h3>
            <button className="small" onClick={() => setAdding(!adding)}>+ New payee</button></div>
          {adding && (
            <div className="card flat col" style={{ padding: 10 }}>
              <small>Quick add (from the demo story):</small>
              {suggested.map((s) => (
                <button key={s.account} className="small" style={{ textAlign: "left" }} onClick={() => addPayee(s)}>
                  {s.display_name} · <span className="mono">{s.account}</span> <small>({s.hint})</small>
                </button>
              ))}
              <div className="row">
                <input placeholder="Name" value={newPayee.display_name} onChange={(e) => setNewPayee({ ...newPayee, display_name: e.target.value })} />
                <input placeholder="Account / UPI" value={newPayee.account} onChange={(e) => setNewPayee({ ...newPayee, account: e.target.value })} />
                <button className="small primary" disabled={!newPayee.display_name || !newPayee.account} onClick={() => addPayee(newPayee)}>Add</button>
              </div>
            </div>
          )}
          <div className="col" style={{ maxHeight: 210, overflow: "auto" }}>
            {cust?.beneficiaries.map((b) => (
              <div key={b.ben_id} className={`payee ${b.ben_id === benId ? "sel" : ""}`} onClick={() => setBenId(b.ben_id)}>
                <div className="col" style={{ gap: 0 }}>
                  <b>{b.display_name}</b>
                  <small className="mono">{b.account_masked} {b.prior_payment_count === 0 && <Badge tone="warning">new · {ago(b.added_at)}</Badge>}</small>
                </div>
                <small>{b.prior_payment_count} paid</small>
              </div>
            ))}
          </div>
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <label style={{ flex: 1 }}>Amount (₹)<input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
            <label style={{ flex: 1.4 }}>Note<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
          </div>
          <details open>
            <summary><b>Got a message about this payment?</b> <small>(optional, helps us protect you)</small></summary>
            <div className="col" style={{ marginTop: 8 }}>
              <div className="thumbs">
                {samples.map((s) => (
                  <div key={s.id} className={`thumb ${picked.includes(s.id) ? "sel" : ""}`} title={s.title}
                    onClick={() => setPicked(picked.includes(s.id) ? picked.filter((x) => x !== s.id) : [...picked, s.id])}>
                    <img src={s.image_url} alt={s.title} loading="lazy" />
                    <span className="lab"><Badge tone={s.label === "scam" ? "bad" : "ok"}>{s.label}</Badge></span>
                    <div className="cap">{s.title}</div>
                  </div>
                ))}
              </div>
              <textarea placeholder="…or paste the message text here" value={pasted} onChange={(e) => setPasted(e.target.value)} />
              <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
          </details>
          <div className="row">
            <label className="check"><input type="checkbox" checked={onCall} onChange={(e) => setOnCall(e.target.checked)} /> On a phone call now</label>
            <label className="check"><input type="checkbox" checked={newDevice} onChange={(e) => setNewDevice(e.target.checked)} /> New device</label>
          </div>
          <ErrorLine error={err} />
          <button className="primary" style={{ padding: 12, fontSize: 15 }} disabled={busy || !benId || !Number(amount)} onClick={pay}>
            {busy ? <><Spinner /> Checking safety…</> : `Pay ${fmtINR(Number(amount))}`}
          </button>
        </div>
      </div>

      <div className="col" style={{ gap: 16 }}>
        <Card title="Behind the scenes" extra={result && <Link to={`/ts/analyst?assessment=${result.assessment_id}`}>Open in analyst console →</Link>}>
          {!result ? (
            <div className="empty">
              Make a payment on the left. Suggested demo:<br />
              <b>1.</b> + New payee → <i>RK Traders</i>, ₹85,000, tick "On a phone call", attach <i>KYC block threat</i> → <b>HOLD</b><br />
              <b>2.</b> + New payee → <i>Rohan Mehta</i>, ₹85,000, attach <i>New landlord deposit</i> → <b>PASS</b><br />
              <b>3.</b> Pay <i>Mr. S. Kapoor (Landlord)</i> ₹25,000 rent, no message → <b>PASS</b><br />
              <b>4.</b> Switch to <i>Meena Iyer</i> (vulnerable, Hindi) and repeat 1 → explanation in Hindi
            </div>
          ) : (
            <div className="col" style={{ gap: 14 }}>
              <div className="row between">
                <div className="row">
                  <Badge tone={result.final_decision}>{result.final_decision}</Badge>
                  <b>risk {(result.risk * 100).toFixed(1)}%</b>
                  {result.hard_rule && <Badge tone="bad">hard rule: {result.hard_rule}</Badge>}
                  {result.matched_campaigns.map((c: string) => <Badge key={c} tone="brand">campaign {c}</Badge>)}
                </div>
                <small className="mono">{result.latency_ms.total} ms · {result.meta.analyzer} · {result.meta.explainer}</small>
              </div>
              <div className="grid g4">
                <Gauge label="Behaviour" value={result.scores.behaviour} color="var(--info)" />
                <Gauge label="Scam content (Gemini)" value={result.scores.content} color="var(--hold)" />
                <Gauge label="Network intel" value={result.scores.intel} color="#ae3ec9" />
                <Gauge label="Legit context" value={result.scores.legit} color="var(--pass)" />
              </div>
              <div>
                <h4>Signal contributions (log-odds points)</h4>
                <SignalBars signals={result.signals} />
              </div>
              {result.analysis && (
                <div>
                  <h4>Evidence analysis</h4>
                  <p style={{ margin: 0 }}><b>{result.analysis.scam_type.replace(/_/g, " ")}</b> · confidence {Math.round(result.analysis.confidence * 100)}% · {result.analysis.summary}</p>
                </div>
              )}
              <div className="row">
                {Object.entries(result.latency_ms).map(([k, v]) => <Badge key={k}>{k}: {String(v)} ms</Badge>)}
              </div>
            </div>
          )}
        </Card>
      </div>
      {showModal && result && <DecisionModal result={result} onClose={() => { setShowModal(false); load(); }} />}
    </div>
  );
}
