const COLORS: Record<string, string> = {
  behaviour: "var(--info)", content: "var(--hold)", intel: "#ae3ec9", legit: "var(--pass)",
};

export default function SignalBars({ signals, max = 10 }: { signals: any[]; max?: number }) {
  const top = signals.slice(0, max);
  const scale = Math.max(0.5, ...top.map((s) => Math.abs(s.contribution)));
  return (
    <div>
      {top.map((s, i) => (
        <div key={i} className="bar-row" title={s.text}>
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            <b>{s.code}</b> <span className="muted">{s.text}</span>
          </span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(Math.abs(s.contribution) / scale) * 100}%`, background: COLORS[s.component] }} />
          </div>
          <span className="mono" style={{ textAlign: "right" }}>{s.contribution > 0 ? "+" : ""}{s.contribution.toFixed(2)}</span>
        </div>
      ))}
      <div className="legend" style={{ marginTop: 6 }}>
        {Object.entries(COLORS).map(([k, c]) => <span key={k} style={{ ["--c" as any]: c }}>{k}</span>)}
      </div>
    </div>
  );
}
