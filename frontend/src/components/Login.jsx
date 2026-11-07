// The one sign-in form for every login: email and password, or Google where the installation
// has it set up.
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { finishGoogle, useSignInOptions } from "@/api/hooks";
import { BASE } from "@/api/client";
import { Logo } from "@/components/layout/Logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { useInstall } from "@/app/site";
import { useCopy } from "@/copy";
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

const GOOGLE_ERRORS = {
  unknown: "That Google account's email has no login here. Sign in with your email and password, or ask whoever runs your campaign.",
  unverified: "Google has not verified that account's email, so it cannot sign in here.",
  cancelled: "Google sign-in was cancelled.",
  expired: "That Google sign-in took too long or was started elsewhere. Try again.",
  failed: "Google could not be reached. Try again, or sign in with your password.",
  busy: "Too many tries; try later.",
};

// The random value a Google sign-in starts with; only the tab holding it can finish it.
const BIND = "google-sign-in-bind";

function startGoogle() {
  const bind = crypto.randomUUID();
  try {
    sessionStorage.setItem(BIND, bind);
  } catch {
    // Storage blocked: the finish is refused and says to try again.
  }
  window.location.assign(`${BASE}/auth/google/start/?bind=${bind}`);
}

function takeBind() {
  try {
    const bind = sessionStorage.getItem(BIND) || "";
    sessionStorage.removeItem(BIND);
    return bind;
  } catch {
    return "";
  }
}

/** Trades the handoff the Google callback left in the address for the session, once. */
function useGoogleReturn(setError) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const adopt = useAuth((s) => s.adopt);
  const done = useRef(false);
  const handoff = params.get("google");
  const refused = params.get("google_error");
  useEffect(() => {
    if (done.current || (!handoff && !refused)) return;
    done.current = true;
    navigate("/signin", { replace: true });
    if (refused) setError(GOOGLE_ERRORS[refused] || GOOGLE_ERRORS.failed);
    else finishGoogle(handoff, takeBind()).then(adopt, (e) => setError(e.message));
  }, [handoff, refused, navigate, adopt, setError]);
}

function GoogleButton() {
  return (
    <button type="button" onClick={startGoogle} className="flex min-h-[50px] cursor-pointer items-center justify-center gap-3 rounded-lg border border-line bg-white px-4 font-bold text-ink hover:bg-stone">
      <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
        <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.2l7.9 6.2C12.5 13.6 17.8 9.5 24 9.5z" />
        <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.8c4.3-4 6.9-9.9 6.9-17.2z" />
        <path fill="#FBBC05" d="M10.6 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.2C1 16.6 0 20.2 0 24s1 7.4 2.7 10.8l7.9-6.2z" />
        <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.8c-2.1 1.4-4.8 2.3-8.5 2.3-6.2 0-11.5-4.1-13.4-9.9l-7.9 6.2C6.6 42.6 14.6 48 24 48z" />
      </svg>
      Sign in with Google
    </button>
  );
}

export default function Login() {
  const login = useAuth((s) => s.login);
  const google = useSignInOptions().data?.google;
  const copy = useCopy();
  // The words differ by installation, so they wait until it is known which this is.
  const { loading } = useInstall();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useGoogleReturn(setError);

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
          {loading ? null : <p className="text-lead text-[#CFE0D5]">{copy.signInLead}</p>}
        </div>
        <Link to="/" className="font-bold text-accent hover:text-accent">← Back to public site</Link>
      </aside>
      <main className="flex min-w-0 flex-[1_1_520px] items-center justify-center px-6 py-12">
        <div className="flex w-full max-w-[420px] flex-col gap-7">
          <div className="flex flex-col gap-2">
            <h2 className="font-display text-[34px] font-extrabold tracking-[-0.02em]">Sign in</h2>
            {loading ? null : <p className="text-muted-foreground">{copy.signInAccount}</p>}
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
          {google ? (
            <div className="flex flex-col gap-3">
              <span className="flex items-center gap-3 text-small text-muted-foreground"><span className="h-px flex-1 bg-line-2" />or<span className="h-px flex-1 bg-line-2" /></span>
              <GoogleButton />
            </div>
          ) : null}
          <Link to="/forgot-password" className="self-start font-bold">Forgot your password?</Link>
          <div className="flex flex-col gap-1.5 border-t border-line-2 pt-5 text-body text-muted-foreground">
            {loading ? null : <span>{copy.signInJoinAsk} <Link to={copy.join.to} className="font-bold">{copy.join.label}</Link></span>}
            <span>Campaign team without a login? Ask whoever runs your campaign.</span>
          </div>
        </div>
      </main>
    </div>
  );
}
