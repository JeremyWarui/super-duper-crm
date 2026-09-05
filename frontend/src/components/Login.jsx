// src/components/Login.jsx
import React, { useState } from "react";
import { useAuth } from "../store/auth";

const C = {
  ink: "#171C1F",
  paper: "#E9EBE6",
  panel: "#FFFFFF",
  green: "#0B6B3A",
  red: "#B4231F",
  line: "#D7DBD4",
  sub: "#5C655F",
};
const DISPLAY = { fontFamily: "Oswald, Impact, sans-serif" };
const FIELD = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: 8,
  border: `1px solid ${C.line}`,
  fontSize: 14,
  marginTop: 6,
  background: C.panel,
  fontFamily: "inherit",
};

// Feather's eye and eye-off, drawn at the size of the field's text.
function EyeIcon({ open }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {open ? (
        <>
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20C5 20 1 12 1 12a18.45 18.45 0 0 1 5.06-5.94" />
          <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
          <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
          <path d="M1 1l22 22" />
        </>
      ) : (
        <>
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </>
      )}
    </svg>
  );
}

export default function Login() {
  const login = useAuth((s) => s.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.paper,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        fontFamily: "Inter, system-ui, sans-serif",
        color: C.ink,
      }}
    >
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');`}</style>
      <div style={{ width: "100%", maxWidth: 380 }}>
        <div
          style={{
            ...DISPLAY,
            fontSize: 26,
            fontWeight: 700,
            textAlign: "center",
            letterSpacing: 0.5,
          }}
        >
          MZIGO<span style={{ color: C.green }}>·</span>CRM
        </div>
        <div
          style={{
            textAlign: "center",
            color: C.sub,
            fontSize: 13,
            marginTop: 2,
            marginBottom: 20,
          }}
        >
          Sign in to the war room
        </div>
        <div
          style={{
            background: C.panel,
            border: `1px solid ${C.line}`,
            borderRadius: 14,
            padding: 22,
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 600 }}>Username</div>
          <input
            style={FIELD}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            autoFocus
          />
          <div style={{ height: 14 }} />
          <div style={{ fontSize: 13, fontWeight: 600 }}>Password</div>
          <div style={{ position: "relative" }}>
            <input
              type={showPassword ? "text" : "password"}
              style={{ ...FIELD, paddingRight: 42 }}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
            <button
              type="button"
              onClick={() => setShowPassword((shown) => !shown)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              title={showPassword ? "Hide password" : "Show password"}
              style={{
                position: "absolute",
                top: 6,
                right: 1,
                bottom: 1,
                width: 40,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 0,
                border: "none",
                borderRadius: "0 8px 8px 0",
                background: "transparent",
                color: showPassword ? C.green : C.sub,
                cursor: "pointer",
              }}
            >
              <EyeIcon open={showPassword} />
            </button>
          </div>
          {error && (
            <div style={{ color: C.red, fontSize: 12.5, marginTop: 10 }}>
              {error}
            </div>
          )}
          <button
            onClick={submit}
            disabled={busy || !username || !password}
            style={{
              width: "100%",
              marginTop: 18,
              padding: 12,
              borderRadius: 8,
              border: "none",
              background: busy || !username || !password ? C.line : C.green,
              color: "#fff",
              ...DISPLAY,
              fontSize: 16,
              fontWeight: 600,
              cursor: busy ? "default" : "pointer",
            }}
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
