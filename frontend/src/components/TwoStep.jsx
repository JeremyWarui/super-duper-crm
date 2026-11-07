// 2-step sign-in for the signed-in login: set it up with an authenticator app, keep recovery
// codes, and turn it off where the login does not need it.
import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useConfirmTwoStep, useRenewRecoveryCodes, useStartTwoStep, useTurnOffTwoStep, useTwoStep } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { useAuth } from "@/store/auth";

const grouped = (secret) => secret.match(/.{1,4}/g).join(" ");

function Problem({ error }) {
  return error ? <p role="alert" className="text-ui font-semibold text-destructive">{error.message}</p> : null;
}

/** One code field and its button. */
function CodeForm({ label, busyLabel, action, onDone, autoFocus }) {
  const [code, setCode] = useState("");
  const submit = (e) => {
    e.preventDefault();
    action.mutate(code.trim(), { onSuccess: (data) => { setCode(""); onDone?.(data); } });
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
      <Field label="Code from your app" hint="Six digits; a recovery code works too.">
        <Input inputMode="numeric" autoComplete="one-time-code" autoFocus={autoFocus} value={code} onChange={(e) => setCode(e.target.value)} className="max-w-[220px]" />
      </Field>
      <Problem error={action.error} />
      <Button type="submit" shape="rounded" className="self-start" disabled={action.isPending || code.trim().length < 6}>
        {action.isPending ? busyLabel : label}
      </Button>
    </form>
  );
}

function RecoveryCodes({ codes, onDone }) {
  const [copied, setCopied] = useState(false);
  const copy = () => navigator.clipboard?.writeText(codes.join("\n")).then(() => setCopied(true), () => {});
  return (
    <div className="flex flex-col gap-3" role="region" aria-label="Recovery codes">
      <p className="text-ui">
        <strong>Save these recovery codes now.</strong> Each signs you in once if you lose your phone. They are not shown again.
      </p>
      <ul className="grid grid-cols-2 gap-x-6 gap-y-1 rounded-lg bg-stone p-4 font-mono text-ui sm:max-w-[360px]">
        {codes.map((c) => <li key={c}>{c}</li>)}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button type="button" shape="rounded" variant="quiet" onClick={copy}>{copied ? "Copied" : "Copy codes"}</Button>
        <Button type="button" shape="rounded" onClick={onDone}>I have saved them</Button>
      </div>
    </div>
  );
}

function SetUp({ onCodes }) {
  const start = useStartTwoStep();
  const confirm = useConfirmTwoStep();
  if (!start.data) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-ui text-muted-foreground">You need an authenticator app on your phone, such as Google Authenticator, Microsoft Authenticator or 1Password.</p>
        <Problem error={start.error} />
        <Button shape="rounded" className="self-start" disabled={start.isPending} onClick={() => start.mutate(undefined)}>
          {start.isPending ? "Starting…" : "Set up 2-step sign-in"}
        </Button>
      </div>
    );
  }
  const { secret, uri } = start.data;
  return (
    <div className="flex flex-col gap-4">
      <ol className="flex list-decimal flex-col gap-1 pl-5 text-ui">
        <li>In your authenticator app, add an account and scan this code.</li>
        <li>Type the six digits the app shows.</li>
      </ol>
      <div className="flex flex-wrap items-center gap-5">
        <span className="rounded-lg border border-line bg-white p-2">
          <QRCodeSVG value={uri} size={176} marginSize={1} title="QR code for your authenticator app" />
        </span>
        <span className="flex flex-col gap-1 text-small">
          <span className="text-muted-foreground">Can't scan it? Type this key:</span>
          <code className="font-mono text-ui font-bold tracking-wide" aria-label="Setup key">{grouped(secret)}</code>
        </span>
      </div>
      <CodeForm label="Turn on" busyLabel="Checking…" action={confirm} onDone={onCodes} autoFocus />
    </div>
  );
}

export default function TwoStep() {
  const status = useTwoStep();
  const renew = useRenewRecoveryCodes();
  const off = useTurnOffTwoStep();
  const [codes, setCodes] = useState(null);
  const [panel, setPanel] = useState(null);

  // Turning it on hands back this session's new token, now marked as past 2-step.
  const passed = ({ codes: fresh, token }) => {
    setCodes(fresh);
    setPanel(null);
    const { user, token: current } = useAuth.getState();
    if (user) useAuth.setState({ token: token || current, user: { ...user, two_step_on: true, two_step_needed: false } });
  };

  if (status.isLoading) return <p className="text-muted-foreground">Checking…</p>;
  if (status.error) return <Problem error={status.error} />;
  const { on, required, recovery_left } = status.data;

  return (
    <Card variant="outline" className="gap-4" role="region" aria-label="2-step sign-in">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-card-title font-bold">2-step sign-in</h2>
        <Badge tone={on ? "ok" : required ? "warn" : "stone"}>{on ? "On" : "Off"}</Badge>
      </div>
      {codes ? (
        <RecoveryCodes codes={codes} onDone={() => setCodes(null)} />
      ) : on ? (
        <>
          <p className="text-ui text-muted-foreground">
            Signing in with your password also asks for a code from your app. {recovery_left} recovery code{recovery_left === 1 ? "" : "s"} left.
          </p>
          {panel === null && (
            <div className="flex flex-wrap gap-2">
              <Button shape="rounded" variant="quiet" onClick={() => setPanel("renew")}>New recovery codes</Button>
              {!required && <Button shape="rounded" variant="quiet" onClick={() => setPanel("off")}>Turn off</Button>}
            </div>
          )}
          {panel === "renew" && <CodeForm label="Make new codes" busyLabel="Making…" action={renew} onDone={passed} autoFocus />}
          {panel === "off" && <CodeForm label="Turn off 2-step" busyLabel="Turning off…" action={off} onDone={() => setPanel(null)} autoFocus />}
          {required && <p className="text-small text-muted-foreground">Your login needs 2-step sign-in, so it stays on.</p>}
        </>
      ) : (
        <>
          <p className="text-ui">
            {required
              ? "Your login needs 2-step sign-in before it can open anything. Set it up now."
              : "Add a code from your phone to every sign-in, so a stolen password is not enough."}
          </p>
          <SetUp onCodes={passed} />
        </>
      )}
    </Card>
  );
}
