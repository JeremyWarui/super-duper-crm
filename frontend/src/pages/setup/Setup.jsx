// First-run setup: a one-time token, then six steps that make the installation in one go.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useCheckSetupToken, useRunSetup, useSetupAreas, useSetupServices, useTestService } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Check, Field, Input, NativeSelect, Textarea } from "@/components/ui/input";
import { INK, MIN_CONTRAST, WHITE, contrast, isHex } from "@/lib/contrast";
import { ColourFields } from "@/components/Swatch";
import { cn } from "@/lib/utils";
import { useAuth } from "@/store/auth";
import { isEmail } from "@/lib/email";
import { isUsername } from "@/lib/username";
import { ErrorText } from "@/components/ui/error-text";
import { NO_PLACE, PlaceSelects } from "@/components/PlaceCascade";
import { SEAT_AREA, SEATS } from "@/lib/labels";
import LoginFields from "@/components/LoginFields";

const STEPS = ["Type", "Name and colours", "Contacts", "First superuser", "Workspace", "Check and finish"];

const BLANK = {
  organisation_type: "",
  site: { name: "", short_name: "", logo_url: "", primary_colour: "#0B5D3B", secondary_colour: "#F2B705", contact_email: "", contact_phone: "", address: "", privacy_notice: "" },
  superuser: { username: "", email: "", password: "", first_name: "", last_name: "" },
  confirm: "",
  aspirant: { title: "", seat: "mca", election_date: "", county: "", constituency: "", ward: "", candidate: { username: "", email: "", first_name: "", last_name: "" } },
  openWorkspace: false,
  manager: { username: "", email: "", first_name: "", last_name: "" },
};

const loginOk = (l) => isUsername(l.username) && isEmail(l.email);

/** Why a step can't go on yet, or null when it can. */
function blocker(step, f) {
  if (step === 0) return f.organisation_type ? null : "Pick party or aspirant.";
  if (step === 1) {
    const { name, primary_colour: p, secondary_colour: s, logo_url: logo } = f.site;
    if (!name.trim()) return "Give the organisation's name.";
    if (logo && !logo.startsWith("https://")) return "The logo link must start with https://.";
    if (!isHex(p) || !isHex(s)) return "Colours are #rrggbb.";
    if (contrast(p, WHITE) < MIN_CONTRAST) return "The primary colour is too light for white text; pick a darker one.";
    if (contrast(s, INK) < MIN_CONTRAST) return "The secondary colour is too dark for dark text; pick a lighter one.";
    return null;
  }
  if (step === 2) return f.site.contact_email && !isEmail(f.site.contact_email) ? "That contact email doesn't look right." : null;
  if (step === 3) {
    const u = f.superuser;
    if (!isUsername(u.username)) return "A username of 3 or more letters, digits, dots, dashes or underscores.";
    if (!isEmail(u.email)) return "An email to sign in with.";
    if (u.password.length < 8) return "A password of at least 8 characters.";
    return u.password === f.confirm ? null : "The two passwords differ.";
  }
  if (step === 4) {
    if (f.organisation_type === "party") return !f.openWorkspace || loginOk(f.manager) ? null : "The Workspace Manager needs a username and an email.";
    const a = f.aspirant;
    const level = SEAT_AREA[a.seat];
    if (!a.title.trim()) return "Name the campaign.";
    if (!a[level]) return `Pick the ${level}.`;
    return loginOk(a.candidate) ? null : "The candidate needs a username and an email.";
  }
  return null;
}

function body(token, f) {
  const out = { token, organisation_type: f.organisation_type, site: f.site, superuser: f.superuser };
  if (f.organisation_type === "aspirant") {
    const a = f.aspirant;
    const level = SEAT_AREA[a.seat];
    out.aspirant = { title: a.title, seat: a.seat, election_date: a.election_date || null, [level]: a[level], candidate: a.candidate };
  } else if (f.openWorkspace) {
    out.party_workspace = f.manager;
  }
  return out;
}

function Choice({ selected, onPick, title, children }) {
  return (
    <button type="button" aria-pressed={selected} onClick={onPick}
      className={cn("flex cursor-pointer flex-col gap-1 rounded-xl border-2 bg-white p-5 text-left", selected ? "border-primary" : "border-line")}>
      <span className="text-card-title font-bold">{title}</span>
      <span className="text-ui text-muted-foreground">{children}</span>
    </button>
  );
}

// The candidate's or manager's login, two boxes to a row.
function Login({ value, onChange, who }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <LoginFields who={who} emailHint="Their sign-in link goes here." fields={["first_name", "last_name", "username", "email"]} form={value} set={(key) => (e) => onChange({ ...value, [key]: e.target.value })} />
    </div>
  );
}

// The seat's area, down to `level`, from the places the setup token can read.
function AreaPicker({ token, level, place, onChange }) {
  const counties = useSetupAreas(token, "county", null);
  const constituencies = useSetupAreas(token, "constituency", place.county);
  const wards = useSetupAreas(token, "ward", place.constituency);
  const loading = { county: counties.isLoading, constituency: constituencies.isLoading, ward: wards.isLoading };
  const lists = { counties: counties.data, constituencies: constituencies.data, wards: wards.data };
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-3">
        <PlaceSelects labelled level={level} place={place} onChange={onChange} lists={lists} blank={(lv) => (loading[lv] ? "Loading…" : `Pick the ${lv}`)} />
      </div>
      {!counties.isLoading && counties.data?.length === 0 && <span className="text-small font-semibold text-destructive">No counties loaded. Run <code>campaign-crm seed</code> first.</span>}
    </>
  );
}

function SeatStep({ token, form, change }) {
  const a = form.aspirant;
  const set = (patch) => change({ aspirant: { ...a, ...patch } });
  const level = SEAT_AREA[a.seat];
  return (
    <div className="flex flex-col gap-4">
      <Field label="Campaign name" hint="Shown in the workspace, e.g. Jane for Parklands."><Input value={a.title} onChange={(e) => set({ title: e.target.value })} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Seat">
          <NativeSelect value={a.seat} onChange={(e) => set({ seat: e.target.value, ...NO_PLACE })}>
            {SEATS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </NativeSelect>
        </Field>
        <Field label="Election date"><Input type="date" value={a.election_date} onChange={(e) => set({ election_date: e.target.value })} /></Field>
      </div>
      <AreaPicker token={token} level={level} place={a} onChange={({ county, constituency, ward }) => set({ county, constituency, ward })} />
      <CardTitle as="h3">The candidate's login</CardTitle>
      <Login who="Candidate" value={a.candidate} onChange={(candidate) => set({ candidate })} />
    </div>
  );
}

function Services({ result }) {
  const signedIn = Boolean(useAuth((s) => s.token));
  const services = useSetupServices(signedIn).data || result.services;
  const test = useTestService();
  const [said, setSaid] = useState({});
  const run = (key) => test.mutate(key, {
    onSuccess: (r) => setSaid((s) => ({ ...s, [key]: { ok: true, text: r.message } })),
    onError: (e) => setSaid((s) => ({ ...s, [key]: { ok: false, text: e.message } })),
  });
  return (
    <Card variant="outline" className="gap-3" role="region" aria-label="Outside services">
      <CardTitle>Outside services</CardTitle>
      <p className="text-ui text-muted-foreground">Set in the server's <code>.env</code>. Practice mode records what would go out and sends nothing.</p>
      <ul className="flex flex-col">
        {services.map((s) => (
          <li key={s.key} className="flex flex-wrap items-center justify-between gap-3 border-t border-line-soft py-3">
            <span className="flex flex-col">
              <span className="font-semibold">{s.label}</span>
              {said[s.key] && <span role="status" className={cn("text-small", said[s.key].ok ? "text-primary" : "text-destructive")}>{said[s.key].text}</span>}
            </span>
            <span className="flex items-center gap-2">
              <Badge tone={s.live ? "ok" : "warn"}>{s.live ? s.mode : `Practice (${s.mode})`}</Badge>
              {s.testable && signedIn && <Button shape="rounded" size="sm" variant="quiet" disabled={test.isPending} onClick={() => run(s.key)} aria-label={`Test ${s.label}`}>Test</Button>}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Done({ result, form }) {
  const login = useAuth((s) => s.login);
  const token = useAuth((s) => s.token);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const invites = result.invites.length;
  const signIn = () => {
    setBusy(true);
    login(form.superuser.email, form.superuser.password).catch((e) => setError(e.message)).finally(() => setBusy(false));
  };
  return (
    <div className="flex flex-col gap-4">
      <Card variant="outline" className="gap-2" role="status">
        <h2 className="font-display text-[26px] font-extrabold">Set up.</h2>
        <p>{form.site.name} is {result.organisation_type === "aspirant" ? "an aspirant" : "a party"} installation, fixed for good. The superuser <strong>{result.superuser}</strong> can sign in now.</p>
        {invites > 0 && <p className="text-ui text-muted-foreground">{result.invites.every((i) => i === "email") ? "A sign-in link went by email to the new workspace login." : "The new workspace login has no email; reset its password from the console."}</p>}
      </Card>
      {!token && (
        <Card variant="outline" className="gap-3">
          <p className="text-ui">Sign in as the superuser to test email and SMS from here.</p>
          <ErrorText error={error} className="text-ui" />
          <Button shape="rounded" className="self-start" disabled={busy} onClick={signIn}>{busy ? "Signing in…" : "Sign in and test"}</Button>
        </Card>
      )}
      <Services result={result} />
      <Link to="/" reloadDocument className="self-start font-bold">Open the site</Link>
    </div>
  );
}

export default function Setup() {
  const queryClient = useQueryClient();
  const checkToken = useCheckSetupToken();
  const runSetup = useRunSetup();
  const [token, setToken] = useState("");
  const [opened, setOpened] = useState(false);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(BLANK);
  const change = (patch) => setForm((f) => ({ ...f, ...patch }));
  const site = (key) => (e) => change({ site: { ...form.site, [key]: typeof e === "string" ? e : e.target.value } });
  const user = (key) => (e) => change({ superuser: { ...form.superuser, [key]: e.target.value } });
  const block = blocker(step, form);

  if (runSetup.isSuccess) return <Frame><Done result={runSetup.data} form={form} /></Frame>;

  if (!opened) {
    return (
      <Frame>
        <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); checkToken.mutate(token.trim(), { onSuccess: () => setOpened(true) }); }}>
          <p className="text-muted-foreground">On the server, run <code className="rounded bg-stone px-1.5 py-0.5">campaign-crm setup-token</code> and paste the token it prints. It works once, for 24 hours.</p>
          <Field label="Setup token"><Input size="lg" autoComplete="off" autoFocus value={token} onChange={(e) => setToken(e.target.value)} /></Field>
          <ErrorText error={checkToken.error} className="text-ui" />
          <Button type="submit" size="lg" disabled={!token.trim() || checkToken.isPending}>{checkToken.isPending ? "Checking…" : "Start setup"}</Button>
        </form>
      </Frame>
    );
  }

  const finish = () => runSetup.mutate(body(token.trim(), form), { onSuccess: () => queryClient.invalidateQueries({ queryKey: ["site"] }) });
  return (
    <Frame>
      <ol aria-label="Steps" className="flex flex-wrap gap-1.5">
        {STEPS.map((label, i) => (
          <li key={label} aria-current={i === step ? "step" : undefined}
            className={cn("rounded-full px-3 py-1 text-small font-bold", i === step ? "bg-primary text-primary-foreground" : i < step ? "bg-primary-tint text-primary" : "bg-stone text-muted-foreground")}>
            {i + 1}. {label}
          </li>
        ))}
      </ol>
      <Card variant="outline" className="gap-5">
        <h2 className="text-[22px] font-extrabold">{STEPS[step]}</h2>
        {step === 0 && (
          <div className="flex flex-col gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Choice selected={form.organisation_type === "party"} onPick={() => change({ organisation_type: "party" })} title="A party">Members, branches, aspirants and the party workspace.</Choice>
              <Choice selected={form.organisation_type === "aspirant"} onPick={() => change({ organisation_type: "aspirant" })} title="An aspirant">One candidate's website and campaign workspace.</Choice>
            </div>
            <p className="text-ui font-semibold text-warn-foreground">This is fixed for good once setup finishes.</p>
          </div>
        )}
        {step === 1 && (
          <div className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Name"><Input value={form.site.name} onChange={site("name")} /></Field>
              <Field label="Short name" hint="Up to 30 letters, for small screens. 3 letters or fewer go on the logo tile; longer, the initials do."><Input value={form.site.short_name} onChange={site("short_name")} /></Field>
            </div>
            <Field label="Logo link" hint="An https:// address of the logo image; you can change it later."><Input type="url" value={form.site.logo_url} onChange={site("logo_url")} /></Field>
            <ColourFields form={form.site} set={site} />
          </div>
        )}
        {step === 2 && (
          <div className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Contact email"><Input type="email" value={form.site.contact_email} onChange={site("contact_email")} /></Field>
              <Field label="Contact phone"><Input type="tel" value={form.site.contact_phone} onChange={site("contact_phone")} /></Field>
            </div>
            <Field label="Address"><Input value={form.site.address} onChange={site("address")} /></Field>
            <Field label="Privacy notice" hint="Shown on /privacy and agreed to at every sign-up form."><Textarea rows={8} value={form.site.privacy_notice} onChange={site("privacy_notice")} /></Field>
          </div>
        )}
        {step === 3 && (
          <div className="flex flex-col gap-4">
            <p className="text-ui text-muted-foreground">The first console login. It manages logins, workspaces and the site.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <LoginFields fields={["first_name", "last_name", "username", "email"]} form={form.superuser} set={user} />
              <Field label="Password" hint="At least 8 characters."><Input type="password" autoComplete="new-password" value={form.superuser.password} onChange={user("password")} /></Field>
              <Field label="Password again"><Input type="password" autoComplete="new-password" value={form.confirm} onChange={(e) => change({ confirm: e.target.value })} /></Field>
            </div>
          </div>
        )}
        {step === 4 && form.organisation_type === "aspirant" && <SeatStep token={token.trim()} form={form} change={change} />}
        {step === 4 && form.organisation_type === "party" && (
          <div className="flex flex-col gap-4">
            <Check className="items-center font-semibold" checked={form.openWorkspace} onChange={(e) => change({ openWorkspace: e.target.checked })}>
              Open the party workspace now, with its first Workspace Manager
            </Check>
            {form.openWorkspace ? <Login who="Manager" value={form.manager} onChange={(manager) => change({ manager })} /> : <p className="text-ui text-muted-foreground">You can open it later from the console.</p>}
          </div>
        )}
        {step === 5 && (
          <dl className="grid gap-x-6 gap-y-2 text-ui sm:grid-cols-[max-content_1fr]">
            <dt className="text-muted-foreground">Type</dt><dd className="font-semibold capitalize">{form.organisation_type}</dd>
            <dt className="text-muted-foreground">Name</dt><dd className="font-semibold">{form.site.name}</dd>
            <dt className="text-muted-foreground">Superuser</dt><dd className="font-semibold">{form.superuser.username} · {form.superuser.email}</dd>
            {form.organisation_type === "aspirant" ? (
              <><dt className="text-muted-foreground">Workspace</dt><dd className="font-semibold">{form.aspirant.title}, candidate {form.aspirant.candidate.username}</dd></>
            ) : (
              <><dt className="text-muted-foreground">Party workspace</dt><dd className="font-semibold">{form.openWorkspace ? `Open, managed by ${form.manager.username}` : "Not yet"}</dd></>
            )}
          </dl>
        )}
        {block && step < 5 && <p className="text-ui text-muted-foreground">{block}</p>}
        <ErrorText error={runSetup.error} className="text-ui" />
        <div className="flex flex-wrap justify-between gap-2">
          <Button shape="rounded" variant="quiet" disabled={step === 0 || runSetup.isPending} onClick={() => setStep(step - 1)}>Back</Button>
          {step < 5
            ? <Button shape="rounded" disabled={Boolean(block)} onClick={() => setStep(step + 1)}>Next</Button>
            : <Button shape="rounded" disabled={runSetup.isPending} onClick={finish}>{runSetup.isPending ? "Setting up…" : "Finish setup"}</Button>}
        </div>
      </Card>
    </Frame>
  );
}

function Frame({ children }) {
  return (
    <main className="min-h-dvh bg-ground-app">
      <section className="mx-auto flex w-full max-w-[760px] flex-col gap-6 px-4 py-12">
        <div className="flex flex-col gap-1">
          <span className="text-meta font-extrabold tracking-[0.08em] text-primary uppercase">First-run setup</span>
          <h1 className="font-display text-[34px] font-extrabold tracking-[-0.02em]">Set up this installation</h1>
        </div>
        {children}
      </section>
    </main>
  );
}
