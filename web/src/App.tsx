import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { firebaseEnabled, onUser, signIn, signOut } from "./shared/auth";
import { Badge, useHealth } from "./shared/ui";
import PayPage from "./trustshield/PayPage";
import AnalystPage from "./trustshield/AnalystPage";
import IntelPage from "./trustshield/IntelPage";
import InsightsPage from "./trustshield/InsightsPage";

export default function App() {
  const health = useHealth();
  const [user, setUser] = useState<string | null>(null);
  useEffect(() => {
    if (!firebaseEnabled) return;
    let off: (() => void) | undefined;
    onUser((u) => setUser(u?.email ?? null)).then((f) => (off = f));
    return () => off?.();
  }, []);
  const live = health?.config?.gemini_backend && health.config.gemini_backend !== "mock";

  if (firebaseEnabled && !user) {
    return (
      <div className="page" style={{ maxWidth: 480, paddingTop: 80 }}>
        <div className="card col" style={{ alignItems: "center", gap: 14 }}>
          <h1>TrustShield</h1>
          <p className="muted">Sign in to open the demo.</p>
          <button className="primary" onClick={() => signIn()}>Sign in with Google</button>
        </div>
      </div>
    );
  }

  return (
    <>
      <header className="topbar">
        <NavLink to="/ts/pay" className="logo"><span className="mark">◆</span> TrustShield</NavLink>
        <nav className="nav">
          <NavLink to="/ts/pay">New payment</NavLink>
          <NavLink to="/ts/analyst">Analyst</NavLink>
          <NavLink to="/ts/intel">Scam intel</NavLink>
          <NavLink to="/ts/insights">Insights</NavLink>
        </nav>
        <span className="spacer" />
        <span className="synthetic">SYNTHETIC DATA</span>
        {health && (
          <Badge tone={live ? "ok" : "warning"}>
            {live ? `Gemini · ${health.config.fast_model}` : "Offline mock (no Gemini)"}
          </Badge>
        )}
        {firebaseEnabled && user && <button className="small ghost" onClick={() => signOut()}>{user} · Sign out</button>}
      </header>
      <Routes>
        <Route path="/" element={<PayPage />} />
        <Route path="/ts/pay" element={<PayPage />} />
        <Route path="/ts/analyst" element={<AnalystPage />} />
        <Route path="/ts/analyst/:caseId" element={<AnalystPage />} />
        <Route path="/ts/intel" element={<IntelPage />} />
        <Route path="/ts/insights" element={<InsightsPage />} />
      </Routes>
    </>
  );
}
