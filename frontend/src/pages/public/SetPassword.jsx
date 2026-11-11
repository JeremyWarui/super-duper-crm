// Opens an invite or reset link: shows whose login it sets, takes the new password twice, and
// signs the person in.
import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useClaimLink, useLink } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { landingOf } from "@/lib/home";
import { useAuth } from "@/store/auth";
import { ErrorText } from "@/components/ui/error-text";

const MIN = 8;

export default function SetPassword() {
  const { token } = useParams();
  const adopt = useAuth((s) => s.adopt);
  const signedIn = useAuth((s) => s.user);
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const claim = useClaimLink(token);
  const link = useLink(token, claim.isIdle);
  if (claim.isSuccess) return <Navigate to={landingOf(signedIn)} replace />;

  const short = password.length > 0 && password.length < MIN;
  const differ = again.length > 0 && again !== password;
  const ready = password.length >= MIN && again === password;
  const invite = link.data?.purpose === "invite";
  const submit = (e) => {
    e.preventDefault();
    if (ready) claim.mutate(password, { onSuccess: adopt });
  };
  return (
    <section className="mx-auto flex w-full max-w-[460px] flex-col gap-6 px-4 py-16">
      {link.isLoading && <p className="text-muted-foreground">Checking your link…</p>}
      {link.error && (
        <>
          <h1 className="font-display text-[34px] font-extrabold tracking-[-0.02em]">This link no longer works</h1>
          <ErrorText error={link.error} className="font-normal text-muted-foreground" />
          <Link to="/forgot-password" className="self-start font-bold">Send a new link</Link>
        </>
      )}
      {link.data && (
        <>
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-[34px] font-extrabold tracking-[-0.02em]">{invite ? "Choose your password" : "Choose a new password"}</h1>
            <p className="text-muted-foreground">
              For the login <b className="text-ink">{link.data.username}</b>{link.data.email ? <>, signing in as {link.data.email}</> : null}.
            </p>
          </div>
          <form onSubmit={submit} className="flex flex-col gap-[18px]" noValidate>
            <Field label="New password">
              <Input size="lg" type="password" autoComplete="new-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            {short && <p className="text-small text-muted-foreground">At least {MIN} characters.</p>}
            <Field label="The same password again">
              <Input size="lg" type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
            </Field>
            {differ && <p className="text-small font-semibold text-destructive">The two passwords differ.</p>}
            <ErrorText error={claim.error} className="text-ui" />
            <Button type="submit" size="lg" disabled={claim.isPending || !ready}>{claim.isPending ? "Saving…" : "Save and sign in"}</Button>
          </form>
        </>
      )}
    </section>
  );
}
