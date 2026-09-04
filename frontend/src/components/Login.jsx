// src/components/Login.jsx
import React, { useState } from "react";
import { useAuth } from "../store/auth";

const C = { ink: "#171C1F", paper: "#E9EBE6", panel: "#FFFFFF", green: "#0B6B3A", red: "#B4231F", line: "#D7DBD4", sub: "#5C655F" };
const DISPLAY = { fontFamily: "Oswald, Impact, sans-serif" };
const FIELD = { width: "100%", padding: "10px 12px", borderRadius: 8, border: `1px solid ${C.line}`, fontSize: 14, marginTop: 6, background: C.panel, fontFamily: "inherit" };

export default function Login() {
  const login = useAuth((s) => s.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError(""); setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: C.paper, display: "flex", alignItems: "center", justifyContent: "center", padding: 16, fontFamily: "Inter, system-ui, sans-serif", color: C.ink }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');`}</style>
      <div style={{ width: "100%", maxWidth: 380 }}>
        <div style={{ ...DISPLAY, fontSize: 26, fontWeight: 700, textAlign: "center", letterSpacing: 0.5 }}>
          MZIGO<span style={{ color: C.green }}>·</span>CRM
        </div>
        <div style={{ textAlign: "center", color: C.sub, fontSize: 13, marginTop: 2, marginBottom: 20 }}>Sign in to the war room</div>
        <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 14, padding: 22 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Username</div>
          <input style={FIELD} value={username} onChange={(e) => setUsername(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} autoFocus />
          <div style={{ height: 14 }} />
          <div style={{ fontSize: 13, fontWeight: 600 }}>Password</div>
          <input type="password" style={FIELD} value={password} onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
          {error && <div style={{ color: C.red, fontSize: 12.5, marginTop: 10 }}>{error}</div>}
          <button onClick={submit} disabled={busy || !username || !password}
            style={{ width: "100%", marginTop: 18, padding: 12, borderRadius: 8, border: "none", background: busy || !username || !password ? C.line : C.green, color: "#fff", ...DISPLAY, fontSize: 16, fontWeight: 600, cursor: busy ? "default" : "pointer" }}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
