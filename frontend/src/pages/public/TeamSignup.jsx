// The public team sign-up behind a workspace's team link: a mobilizer picks a ward (or a centre
// in an MCA race), an agent a registration centre; the campaign approves before they sign in.
import { useParams } from "react-router-dom";
import { useSignupCentres, useSubmitSignup, useTeamSignup } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Check, Field, Input, NativeSelect } from "@/components/ui/input";
import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";
import { StatusText } from "@/components/ui/notice";
import { useForm } from "@/lib/form";

const ROLES = [
  ["mobilizer", "Mobilizer", "Recruit supporters and run events in your area."],
  ["agent", "Agent", "Get vetted and trained as a polling agent for one registration centre."],
];

function WardSelect({ wards, value, onChange }) {
  const counties = [...new Set(wards.map((w) => w.county_name))];
  const option = (w) => <option key={w.id} value={w.id}>{w.name}</option>;
  return (
    <NativeSelect size="lg" aria-label="Ward" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Pick your ward</option>
      {counties.length > 1
        ? counties.map((county) => <optgroup key={county} label={county}>{wards.filter((w) => w.county_name === county).map(option)}</optgroup>)
        : wards.map(option)}
    </NativeSelect>
  );
}

export default function TeamSignup() {
  const { code } = useParams();
  const page = useTeamSignup(code);
  const submit = useSubmitSignup(code);
  const [form, setForm, set] = useForm({ role: "mobilizer", first_name: "", last_name: "", phone: "", email: "", id_number: "", ward: "", registration_centre: "", consent_given: false });
  const data = page.data;
  const wantsCentre = form.role === "agent" || data?.mobilizer_place === "centre";
  const centres = useSignupCentres(code, wantsCentre ? form.ward : "");
  const ready = form.first_name.trim() && form.phone.trim() && form.email.trim() && form.id_number.trim() && form.ward && (!wantsCentre || form.registration_centre) && form.consent_given;
  const send = (e) => {
    e.preventDefault();
    if (!ready) return;
    submit.mutate({
      role: form.role, first_name: form.first_name, last_name: form.last_name, phone: form.phone, email: form.email,
      id_number: form.id_number, consent_given: true,
      ward: wantsCentre ? null : form.ward, registration_centre: wantsCentre ? form.registration_centre : null,
    });
  };

  return (
    <section className="mx-auto flex w-full max-w-[560px] flex-col gap-6 px-4 py-16">
      {page.isLoading && <LoadingText />}
      {page.error && (
        <>
          <h1 className="font-display text-[34px] font-extrabold tracking-[-0.02em]">This link does not work</h1>
          <ErrorText error={`${page.error.message} Ask the campaign for its current team link.`} className="font-normal text-muted-foreground" />
        </>
      )}
      {data && (
        <>
          <div className="flex flex-col gap-2">
            <p className="text-ui font-semibold text-primary">{data.campaign_title} · {data.seat_label}</p>
            <h1 className="font-display text-[34px] font-extrabold tracking-[-0.02em]">Join the campaign team</h1>
            <p className="text-muted-foreground">The campaign reviews every sign-up. Once approved you get an email with a link to choose your password.</p>
          </div>
          {submit.isSuccess ? (
            <StatusText boxed>{submit.data.message}</StatusText>
          ) : !data.open ? (
            <p role="alert" className="rounded-lg bg-warn p-4 font-semibold text-warn-foreground">This campaign is not taking sign-ups right now.</p>
          ) : (
            <form onSubmit={send} className="flex flex-col gap-[18px]" noValidate>
              <fieldset className="flex flex-col gap-2.5">
                <legend className="mb-2 text-ui font-semibold">I want to be</legend>
                {ROLES.map(([value, label, note]) => (
                  <label key={value} className={`flex cursor-pointer gap-3 rounded-lg border-[1.5px] p-3.5 ${form.role === value ? "border-primary bg-primary-tint" : "border-line-control bg-white"}`}>
                    <input type="radio" name="role" value={value} checked={form.role === value} onChange={() => setForm({ ...form, role: value, registration_centre: "" })} className="mt-1 size-[18px] accent-primary" />
                    <span className="flex flex-col"><b>{label}</b><span className="text-small text-muted-foreground">{note}</span></span>
                  </label>
                ))}
              </fieldset>
              <div className="grid gap-[18px] sm:grid-cols-2">
                <Field label="First name"><Input size="lg" autoComplete="given-name" value={form.first_name} onChange={set("first_name")} /></Field>
                <Field label="Last name"><Input size="lg" autoComplete="family-name" value={form.last_name} onChange={set("last_name")} /></Field>
              </div>
              <Field label="Phone"><Input size="lg" type="tel" autoComplete="tel" placeholder="0712 345678" value={form.phone} onChange={set("phone")} /></Field>
              <Field label="Email" hint="You sign in with it."><Input size="lg" type="email" autoComplete="email" value={form.email} onChange={set("email")} /></Field>
              <Field label="ID number" hint="National ID or passport. Only the candidate and campaign manager see it."><Input size="lg" value={form.id_number} onChange={set("id_number")} /></Field>
              <Field label={wantsCentre ? "Ward of your registration centre" : "Ward you will work"}>
                <WardSelect wards={data.wards} value={form.ward} onChange={(ward) => setForm({ ...form, ward, registration_centre: "" })} />
              </Field>
              {wantsCentre && form.ward && (
                <Field label="Registration centre">
                  <NativeSelect size="lg" aria-label="Registration centre" value={form.registration_centre} onChange={set("registration_centre")}>
                    <option value="">{centres.isLoading ? "Loading centres…" : "Pick a centre"}</option>
                    {(centres.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </NativeSelect>
                </Field>
              )}
              <Check className="gap-2.5 text-ui" checked={form.consent_given} onChange={set("consent_given")}>
                <span>{data.consent_wording}</span>
              </Check>
              <ErrorText error={submit.error} className="text-ui" />
              <Button loading={submit.isPending} type="submit" size="lg" disabled={submit.isPending || !ready}>{submit.isPending ? "Sending…" : "Sign up"}</Button>
            </form>
          )}
        </>
      )}
    </section>
  );
}
