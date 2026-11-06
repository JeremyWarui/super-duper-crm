import { useState } from "react";
import { useAuth } from "@/store/auth";
import { useCentres, useConsentWording, useMobilizers, useRegisterSupporter, useTargets } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { useDraft } from "@/lib/draft";
import { cn } from "@/lib/utils";
import SendError from "./SendError";

const BLANK = { full_name: "", phone: "", ward: "", centre: null, support_level: "supporter", consent_given: false };
const LEVELS = [["supporter", "Supporter"], ["undecided", "Undecided"], ["opposed", "Opposed"]];

/**
 * Quick capture in the field. The entry is kept on the device until it is sent. In an MCA race
 * the supporter is filed to a registration centre with a target, the mobilizer's own to start.
 */
export default function RegisterSupporterForm({ campaignId, wardOptions, byCentre }) {
  const reg = useRegisterSupporter();
  const wording = useConsentWording().data?.consent_wording;
  const user = useAuth((s) => s.user);
  const own = (useMobilizers(campaignId).data || []).find((m) => m.user === user?.id);
  const [form, setForm, clear] = useDraft(`register:${campaignId}`, BLANK);
  const [sent, setSent] = useState(false);
  const change = (patch) => setForm((f) => ({ ...f, ...patch }));
  const ward = form.ward || wardOptions[0]?.id || "";
  const centresQuery = useCentres(byCentre ? ward : null);
  const targetsQuery = useTargets(campaignId);
  const targeted = new Set((targetsQuery.data || []).map((t) => t.registration_centre));
  const centres = (centresQuery.data || []).filter((c) => targeted.has(c.id));
  const ownCentre = own?.ward === ward && targeted.has(own?.registration_centre) ? own.registration_centre : null;
  const centre = form.centre ?? ownCentre ?? "";
  const loaded = !centresQuery.isFetching && !centresQuery.isError && targetsQuery.isSuccess;
  const ok = form.full_name.trim() && form.consent_given && ward && (!byCentre || (loaded && centre));
  // The promise settles even if the form has closed meanwhile, so a sent entry never stays kept.
  const send = () => reg.mutateAsync(
    { campaign: campaignId, full_name: form.full_name, phone: form.phone, ward, support_level: form.support_level, consent_given: form.consent_given, registration_centre: centre || null },
  ).then(() => { clear(); setSent(true); }, () => {});

  if (sent) {
    return (
      <Card variant="outline" className="max-w-[560px] gap-3" role="status">
        <p className="text-card-title font-bold">Registered.</p>
        <Button shape="rounded" className="self-start" onClick={() => { reg.reset(); setSent(false); }}>Register another</Button>
      </Card>
    );
  }
  return (
    <Card variant="outline" className="max-w-[560px] gap-4">
      <Field label="Full name"><Input autoComplete="off" value={form.full_name} onChange={(e) => change({ full_name: e.target.value })} /></Field>
      <Field label="Phone"><Input type="tel" inputMode="tel" autoComplete="off" value={form.phone} onChange={(e) => change({ phone: e.target.value })} /></Field>
      <Field label="Ward">
        <NativeSelect value={ward} onChange={(e) => change({ ward: e.target.value, centre: null })}>
          {wardOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </NativeSelect>
      </Field>
      {byCentre && centres.length > 0 && (
        <Field label="Registration centre">
          <NativeSelect aria-label="Registration centre" value={centre} onChange={(e) => change({ centre: e.target.value })}>
            <option value="">Pick a centre</option>
            {centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </NativeSelect>
        </Field>
      )}
      <div className="flex flex-col gap-1.5">
        <span className="text-small font-semibold">Support</span>
        <div role="group" aria-label="Support" className="grid grid-cols-3 gap-2">
          {LEVELS.map(([value, label]) => (
            <button key={value} type="button" aria-pressed={form.support_level === value} onClick={() => change({ support_level: value })}
              className={cn("min-h-11 cursor-pointer rounded-lg border px-2 text-ui font-bold", form.support_level === value ? "border-primary bg-primary text-primary-foreground" : "border-line-control bg-white text-ink")}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <label className="flex min-h-11 items-start gap-3 text-ui">
        <input type="checkbox" className="mt-0.5 size-6 flex-none accent-primary" checked={form.consent_given} onChange={(e) => change({ consent_given: e.target.checked })} />
        <span>{wording}</span>
      </label>
      <SendError error={reg.error} pending={reg.isPending} onRetry={send} />
      <Button shape="rounded" size="lg" className="w-full sm:w-auto sm:self-start" disabled={!ok || !wording || reg.isPending} onClick={send}>
        {reg.isPending ? "Saving…" : "Register supporter"}
      </Button>
      <p className="text-small text-muted-foreground">What you type is kept on this phone until it is sent.</p>
    </Card>
  );
}
