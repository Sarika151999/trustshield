import { getIdToken } from "./auth";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Opts = { method?: string; json?: unknown; form?: FormData };

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Demo-Role": "demo" };
  const token = await getIdToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  const res = await fetch(path, { method: opts.method ?? (body ? "POST" : "GET"), headers, body });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export function form(fields: Record<string, string | Blob>): FormData {
  const f = new FormData();
  Object.entries(fields).forEach(([k, v]) => f.append(k, v));
  return f;
}

export function fmtINR(x: number | null | undefined, signed = false): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  const a = Math.abs(x);
  let s: string;
  if (a >= 1e7) s = `₹${(a / 1e7).toFixed(2)} Cr`;
  else if (a >= 1e5) s = `₹${(a / 1e5).toFixed(1)}L`;
  else s = `₹${Math.round(a).toLocaleString("en-IN")}`;
  if (x < 0) return "-" + s;
  return signed ? "+" + s : s;
}

export const pct = (x: number | null | undefined, d = 0) =>
  x === null || x === undefined ? "–" : `${(x * 100).toFixed(d)}%`;

export const shortDate = (iso?: string | null) =>
  iso ? new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "–";
