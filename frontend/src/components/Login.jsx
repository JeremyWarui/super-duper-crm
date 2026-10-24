import React, { useState } from "react";
import { useAuth } from "../store/auth";

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

function Field({ label, value, onChange, onEnter, ...rest }) {
  return (
    <>
      <div className="login-label">{label}</div>
      <input
        className="login-field"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onEnter()}
        {...rest}
      />
    </>
  );
}

export default function Login() {
  const login = useAuth((s) => s.login);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const ready = username.trim().length > 0 && password.length > 0;

  const submit = async () => {
    if (!ready) return;
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
    <div className="login-shell">
      <div className="login-content">
        <div className="login-brand">
          MZIGO<span className="login-brand-mark">·</span>CRM
        </div>
        <div className="login-subtitle">
          Sign in to the war room
        </div>
        <div className="login-card">
          <Field
            label="Username"
            value={username}
            onChange={setUsername}
            onEnter={submit}
            autoFocus
          />
          <div className="login-field-spacer" />
          <div className="login-label">Password</div>
          <div className="login-password-wrapper">
            <input
              type={showPassword ? "text" : "password"}
              className="login-field login-password-field"
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
              className={`login-password-toggle ${showPassword ? "login-toggle-on" : ""}`}
            >
              <EyeIcon open={showPassword} />
            </button>
          </div>

          {error && (
            <div className="login-error">
              {error}
            </div>
          )}
          <button
            onClick={submit}
            disabled={busy || !ready}
            className={`login-submit ${busy || !ready ? "login-submit-disabled" : "login-submit-ready"}`}
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>

        <div className="login-help">
          No login yet? Ask whoever runs your campaign.
        </div>
      </div>
    </div>
  );
}
