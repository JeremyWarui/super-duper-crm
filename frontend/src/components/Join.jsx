// The public page an event's QR code or a campaign's link opens: sign up as a supporter, no login.
import { useState } from "react";
import { useJoin, useJoinPage } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Field, FilterSelect, Input } from "@/components/ui/input";
import { LoadingText } from "@/components/ui/loading-text";

// The person's own way back off the register; shown once, after signing up.
function WithdrawNote({ code }) {
  const link = `${window.location.origin}/withdraw/${code}`;
  return (
    <p className="text-ui leading-[1.6] text-muted-foreground">
      Changed your mind later? Keep this link. Opening it lets you take your details off the
      register: <a href={link} className="break-all font-semibold">{link}</a>
    </p>
  );
}

export default function Join({ code }) {
  const page = useJoinPage(code);
  const join = useJoin(code);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [place, setPlace] = useState("");
  // A campaign's link asks where the person votes: a ward is required, a centre is optional.
  const ok = name.trim() && phone.trim() && consent && (page.data?.place !== "ward" || place);

  const shell = (children) => (
    <main className="flex min-h-dvh justify-center bg-background px-4 py-[6vh]">
      <Card variant="outline" className="h-fit w-full max-w-[480px]">{children}</Card>
    </main>
  );
  if (page.isLoading) return shell(<LoadingText />);
  if (page.error) return shell(<ErrorText error={page.error} />);
  const p = page.data;
  const heading = (
    <div className="flex flex-col gap-1">
      <h1 className="font-display text-h3 font-extrabold tracking-[-0.02em]">{p.campaign_title}</h1>
      <p className="text-muted-foreground">{p.event_title || p.ward_name}{p.candidate_name ? ` · ${p.candidate_name}` : ""}</p>
    </div>
  );
  if (join.isSuccess) {
    return shell(
      <>
        {heading}
        <p role="status" className="text-lead font-semibold text-primary">{join.data.message}</p>
        <WithdrawNote code={join.data.withdraw_code} />
      </>,
    );
  }
  if (!p.open) return shell(<>{heading}<p className="text-muted-foreground">Sign-ups are closed.</p></>);

  return shell(
    <>
      {heading}
      <Field label="Full name">
        <Input aria-label="Full name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
      </Field>
      <Field label="Phone">
        <Input aria-label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" placeholder="0712 345678" />
      </Field>
      {p.places.length > 0 && (
        <Field label={p.place === "centre" ? "Your registration centre" : "Your ward"}>
          <FilterSelect label="Where you vote" blank={p.place === "centre" ? "Not sure" : "Pick your ward"} value={place} onChange={setPlace} options={p.places} className="w-full flex-none" />
        </Field>
      )}
      <label className="flex cursor-pointer items-start gap-3 text-ui leading-[1.5] text-muted-foreground">
        <input type="checkbox" className="mt-0.5 size-5 flex-none accent-primary" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        {p.consent_wording}
      </label>
      <ErrorText error={join.error} className="text-small" />
      <Button
        className="w-full"
        disabled={!ok || join.isPending}
        onClick={() => join.mutate({ full_name: name.trim(), phone: phone.trim(), consent_given: true, place: place || null })}
      >
        {join.isPending ? "Signing up…" : "Sign up"}
      </Button>
    </>,
  );
}
