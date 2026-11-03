// The one sign-in form for every login: email and password.
import { useState } from "react";
import { Link } from "react-router-dom";
import { Logo } from "@/components/layout/Logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
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

export default function Login() {
  const login = useAuth((s) => s.login);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const ready = email.trim().length > 0 && password.length > 0;

  const submit = async (e) => {
    e.preventDefault();
    if (!ready) return;
    setError("");
    setBusy(true);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-dvh flex-wrap bg-background">
      <aside className="flex min-w-0 flex-[1_1_420px] flex-col justify-between gap-12 bg-primary p-8 text-on-dark sm:p-12">
        <Logo size="md" onPrimary />
        <div className="flex max-w-[440px] flex-col gap-5">
          <h1 className="font-display text-[clamp(36px,4vw,56px)] leading-[1.02] font-extrabold tracking-[-0.02em]">The team behind the movement.</h1>
          <p className="text-lead text-[#CFE0D5]">Members, candidate teams, mobilizers and party staff sign in here. One account, routed to the right place.</p>
        </div>
        <Link to="/" className="font-bold text-accent hover:text-accent">← Back to public site</Link>
      </aside>
      <main className="flex min-w-0 flex-[1_1_520px] items-center justify-center px-6 py-12">
        <div className="flex w-full max-w-[420px] flex-col gap-7">
          <div className="flex flex-col gap-2">
            <h2 className="font-display text-[34px] font-extrabold tracking-[-0.02em]">Sign in</h2>
            <p className="text-muted-foreground">Use the email and password of your party account.</p>
          </div>
          <form onSubmit={submit} className="flex flex-col gap-[18px]" noValidate>
            <Field label="Email">
              <Input size="lg" type="email" autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Field label="Password">
              <span className="relative flex">
                <Input size="lg" type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="pr-12" />
                <button
                  type="button"
                  onClick={() => setShowPassword((shown) => !shown)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  title={showPassword ? "Hide password" : "Show password"}
                  className="absolute top-0 right-0 flex size-[50px] cursor-pointer items-center justify-center rounded-lg text-muted-foreground hover:text-ink"
                >
                  <EyeIcon open={showPassword} />
                </button>
              </span>
            </Field>
            {error ? <p role="alert" className="text-ui font-semibold text-destructive">{error}</p> : null}
            <Button type="submit" size="lg" disabled={busy || !ready}>{busy ? "Signing in…" : "Sign in"}</Button>
          </form>
          <div className="flex flex-col gap-1.5 border-t border-line-2 pt-5 text-body text-muted-foreground">
            <span>Not a member yet? <Link to="/join-party" className="font-bold">Join the party</Link></span>
            <span>Campaign team without a login? Ask whoever runs your campaign.</span>
          </div>
        </div>
      </main>
    </div>
  );
}
