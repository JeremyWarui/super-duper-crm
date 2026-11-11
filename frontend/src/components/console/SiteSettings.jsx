// The console's Settings tab: the site's settings, and in a party installation the party-only ones.
import { useState } from "react";
import { PARTY_FIELDS, useParty, useSaveSettings, useSite } from "@/api/hooks";
import ConfigFields from "@/components/ConfigFields";
import { ColourFields } from "@/components/Swatch";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Input } from "@/components/ui/input";
import { LoadingText } from "@/components/ui/loading-text";
import { SITE_LINES, SITE_TEXTS } from "@/lib/siteFields";
import { Failed, Help } from "./kit";

const MPESA = ["mpesa_paybill", "mpesa_account", "mpesa_till"];
const KEYS = [...SITE_LINES, ...SITE_TEXTS].map(([key]) => key).concat("primary_colour", "secondary_colour");

const formOf = (site) => ({
  ...Object.fromEntries(KEYS.map((key) => [key, site[key] ?? ""])),
  links: Object.entries(site.social_links || {}),
});

function SettingsForm({ site, isParty }) {
  const save = useSaveSettings({ party: isParty });
  const [form, setForm] = useState(() => formOf(site));
  const [saved, setSaved] = useState(false);
  const set = (patch) => {
    setSaved(false);
    setForm((f) => ({ ...f, ...patch }));
  };
  const field = (key) => (e) => set({ [key]: e.target.value });
  const shown = (fields) => fields.filter(([key]) => isParty || !PARTY_FIELDS.includes(key));
  const lines = shown(SITE_LINES);
  const setLink = (i, at, value) => set({ links: form.links.map((pair, j) => (j === i ? pair.map((v, k) => (k === at ? value : v)) : pair)) });

  const submit = () => {
    const { links, ...all } = form;
    const kept = Object.entries(all).filter(([key]) => isParty || !PARTY_FIELDS.includes(key));
    save.mutate(
      {
        ...Object.fromEntries(kept.map(([key, value]) => [key, MPESA.includes(key) ? value.trim() : value])),
        social_links: Object.fromEntries(links.map(([name, url]) => [name.trim(), url.trim()]).filter(([name]) => name)),
      },
      { onSuccess: () => setSaved(true) },
    );
  };

  return (
    <Card variant="outline">
      <CardTitle>{isParty ? "Party settings" : "Site settings"}</CardTitle>
      <div className="grid gap-3 sm:grid-cols-2">
        <ConfigFields fields={lines.filter(([key]) => !MPESA.includes(key))} form={form} set={field} />
        <ColourFields form={form} set={(key) => (value) => set({ [key]: value })} />
      </div>
      <ConfigFields fields={shown(SITE_TEXTS)} form={form} set={field} />
      <div className="flex flex-col gap-2">
        <div className="grid gap-3 sm:grid-cols-3">
          <ConfigFields fields={lines.filter(([key]) => MPESA.includes(key))} form={form} set={field} />
        </div>
        <Help>The Contribute page and the nomination fee offer these to pay by code. Give a Paybill or a Till, not both.</Help>
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-body font-bold">Social links</h3>
        {form.links.map(([name, url], i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <Input className="w-full sm:w-44" aria-label={`Social link ${i + 1} name`} value={name} onChange={(e) => setLink(i, 0, e.target.value)} placeholder="facebook" />
            <Input className="w-full sm:w-auto sm:min-w-56 sm:flex-1" aria-label={`Social link ${i + 1} address`} value={url} onChange={(e) => setLink(i, 1, e.target.value)} placeholder="https://" />
            <Button shape="rounded" size="sm" variant="quiet" onClick={() => set({ links: form.links.filter((_, j) => j !== i) })}>Remove</Button>
          </div>
        ))}
        <div>
          <Button shape="rounded" size="sm" variant="quiet" onClick={() => set({ links: [...form.links, ["", ""]] })}>Add a link</Button>
        </div>
      </div>
      <ErrorText error={save.error} className="text-ui" />
      {saved && <p role="status" className="text-ui font-semibold text-primary">Saved.</p>}
      <div className="flex flex-wrap gap-2">
        <Button shape="rounded" size="sm" disabled={save.isPending} onClick={submit}>
          {save.isPending ? "Saving…" : isParty ? "Save the party settings" : "Save the site settings"}
        </Button>
      </div>
    </Card>
  );
}

export default function SiteSettings() {
  const site = useSite();
  const isParty = site.data?.organisation_type === "party";
  const party = useParty(isParty);
  if (site.isPending || (isParty && party.isPending))
    return <LoadingText>{site.data?.organisation_type === "aspirant" ? "Loading the site settings…" : "Loading the party settings…"}</LoadingText>;
  const failed = [site, ...(isParty ? [party] : [])].find((q) => q.error);
  if (failed) return <Failed error={failed.error} onRetry={() => failed.refetch()} />;
  return <SettingsForm key={`${site.data.updated_at} ${party.data?.updated_at}`} site={{ ...site.data, ...party.data }} isParty={isParty} />;
}
