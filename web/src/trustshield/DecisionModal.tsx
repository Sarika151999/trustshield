import { useEffect, useState } from "react";
import { api, fmtINR } from "../shared/api";

const ICON: Record<string, string> = { PASS: "✓", WARN: "!", HOLD: "⏸" };
const COOL_OFF = 15;

export default function DecisionModal({ result, onClose }: { result: any; onClose: () => void }) {
  const [decision, setDecision] = useState<string>(result.final_decision);
  const [iv, setIv] = useState<any>(result.intervention);
  const [answers, setAnswers] = useState<Record<string, "yes" | "no">>({});
  const [left, setLeft] = useState(COOL_OFF);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (decision !== "WARN") return;
    const t = setInterval(() => setLeft((x) => Math.max(0, x - 1)), 1000);
    return () => clearInterval(t);
  }, [decision]);

  useEffect(() => {
    if (result.final_decision === "PASS") {
      api(`/api/ts/payments/${result.payment_id}/action`, { json: { action: "confirm" } }).then(() => setStatus("completed"));
    }
  }, [result]);

  const qs = iv.safety_questions ?? [];
  const allAnswered = qs.every((q: any) => answers[q.id]);

  const proceed = async () => {
    const r = await api(`/api/ts/assessments/${result.assessment_id}/answers`, { json: { answers } });
    if (r.final_decision === "HOLD") {
      setDecision("HOLD");
      if (r.intervention) setIv(r.intervention);
      return;
    }
    await api(`/api/ts/payments/${result.payment_id}/action`, { json: { action: "confirm" } });
    setStatus("completed");
  };
  const cancel = async () => {
    await api(`/api/ts/payments/${result.payment_id}/action`, { json: { action: "cancel" } });
    setStatus("cancelled");
  };

  if (status) {
    return (
      <div className="overlay" onClick={onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()}>
          <div className={`head ${status === "completed" ? "PASS" : "WARN"}`}>
            <div className={`icon-circle ${status === "completed" ? "PASS" : "WARN"}`}>{status === "completed" ? "✓" : "✕"}</div>
            <div><h2 style={{ margin: 0 }}>{status === "completed" ? `${fmtINR(result.amount)} sent` : "Payment cancelled"}</h2>
              <small>{status === "completed" ? `to ${result.beneficiary.display_name}` : "Your money stays in your account."}</small></div>
          </div>
          <div className="foot"><button className="primary" onClick={onClose}>Done</button></div>
        </div>
      </div>
    );
  }

  return (
    <div className="overlay">
      <div className="modal">
        <div className={`head ${decision}`}>
          <div className={`icon-circle ${decision}`}>{ICON[decision]}</div>
          <div>
            <h2 style={{ margin: 0 }}>{iv.headline}</h2>
            <small>{fmtINR(result.amount)} to {result.beneficiary.display_name}</small>
          </div>
        </div>
        <div className="content">
          {iv.customer_message && <p style={{ margin: 0, fontSize: 15 }}>{iv.customer_message}</p>}
          {iv.why_points?.length > 0 && (
            <div>
              <h4>Why we're concerned</h4>
              <ul style={{ margin: 0, paddingLeft: 18 }}>{iv.why_points.map((w: string, i: number) => <li key={i}>{w}</li>)}</ul>
            </div>
          )}
          {decision === "WARN" && qs.length > 0 && (
            <div className="col">
              <h4>Quick safety check</h4>
              {qs.map((q: any) => (
                <div key={q.id} className="q">
                  <span>{q.text}</span>
                  <span className="seg">
                    {(["yes", "no"] as const).map((v) => (
                      <button key={v} className={answers[q.id] === v ? "on" : ""} onClick={() => setAnswers({ ...answers, [q.id]: v })}>{v}</button>
                    ))}
                  </span>
                </div>
              ))}
            </div>
          )}
          {decision === "HOLD" && (
            <div className="card flat" style={{ background: "var(--surface-2)" }}>
              📞 Call TrustBank on <b>1800-000-0000</b> (the number on your card). Never call a number given in a message.
              <br /><small>Case opened for a fraud analyst · review within 24 h</small>
            </div>
          )}
        </div>
        <div className="foot">
          {decision === "WARN" && (
            <>
              <button onClick={proceed} disabled={left > 0 || !allAnswered}>
                {left > 0 ? `I understand, continue (${left}s)` : "I understand, continue"}
              </button>
              <button className="primary" onClick={cancel}>Cancel payment</button>
            </>
          )}
          {decision === "HOLD" && <button className="primary" onClick={onClose}>OK</button>}
        </div>
      </div>
    </div>
  );
}
