// The one sign-in form for every login: email and password.
import { useState } from "react";
import { Link } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { Logo } from "@/components/layout/Logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { useInstall } from "@/app/site";
import { useCopy } from "@/copy";
import { useAuth } from "@/store/auth";
import { ErrorText } from "@/components/ui/error-text";

export default function Login() {
  const login = useAuth((s) => s.login);
  const copy = useCopy();
  // The words differ by installation, so they wait until it is known which this is.
  const { loading } = useInstall();

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
          {loading ? null : <p className="text-lead text-on-primary-muted">{copy.signInLead}</p>}
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
                  {showPassword ? <EyeOff className="size-[18px]" strokeWidth={1.8} aria-hidden /> : <Eye className="size-[18px]" strokeWidth={1.8} aria-hidden />}
                </button>
              </span>
            </Field>
            <ErrorText error={error} className="text-ui" />
            <Button loading={busy} type="submit" size="lg" disabled={busy || !ready}>{busy ? "Signing in…" : "Sign in"}</Button>
          </form>
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
