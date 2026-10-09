import { ReactNode, useEffect, useState } from "react";
import { api } from "./api";

export function Card(props: { title?: ReactNode; extra?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${props.className ?? ""}`}>
      {(props.title || props.extra) && (
        <div className="row between" style={{ marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>{props.title}</h2>
          {props.extra}
        </div>
      )}
      {props.children}
    </section>
  );
}

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div className="stat">
      <span className="v" style={tone ? { color: `var(--${tone})` } : undefined}>{value}</span>
      <span className="l">{label}</span>
    </div>
  );
}

export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone ?? ""}`}>{children}</span>;
}

export function Spinner() {
  return <span className="spinner" aria-label="loading" />;
}

export function Gauge({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="gauge">
      <div className="row between"><small>{label}</small><b>{Math.round(value * 100)}</b></div>
      <div className="track"><div className="fill" style={{ width: `${Math.min(100, value * 100)}%`, background: color }} /></div>
    </div>
  );
}

/** Tiny, safe markdown renderer: headings, bullets, bold, italics, paragraphs. */
export function Md({ text }: { text: string }) {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (s: string) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|\W)_(.+?)_(?=\W|$)/g, "$1<i>$2</i>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, "$1<i>$2</i>");
  const out: string[] = [];
  let list = false;
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const li = /^\s*[-•]\s+(.*)/.exec(line);
    if (li) {
      if (!list) { out.push("<ul>"); list = true; }
      out.push(`<li>${inline(li[1])}</li>`);
      continue;
    }
    if (list) { out.push("</ul>"); list = false; }
    const h = /^#{1,4}\s+(.*)/.exec(line);
    if (h) out.push(`<h3>${inline(h[1])}</h3>`);
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  if (list) out.push("</ul>");
  return <div className="md" dangerouslySetInnerHTML={{ __html: out.join("") }} />;
}

export function useHealth() {
  const [h, setH] = useState<any>(null);
  useEffect(() => { api("/api/health").then(setH).catch(() => setH(null)); }, []);
  return h;
}

export function ErrorLine({ error }: { error: string | null }) {
  return error ? <div className="err">⚠ {error}</div> : null;
}
