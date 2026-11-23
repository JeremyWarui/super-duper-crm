// The console's Settings tab: the site's settings.
import { useState } from "react";
import { useSaveSettings, useSite } from "@/api/hooks";
import ConfigFields from "@/components/ConfigFields";
import { ColourFields } from "@/components/Swatch";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Input } from "@/components/ui/input";
import { LoadingText } from "@/components/ui/loading-text";
import { SITE_LINES, SITE_TEXTS } from "@/lib/siteFields";
import { Failed, Help } from "./kit";
import { StatusText } from "@/components/ui/notice";

const MPESA = ["mpesa_paybill", "mpesa_account", "mpesa_till"];
const KEYS = [...SITE_LINES, ...SITE_TEXTS].map(([key]) => key).concat("primary_colour", "secondary_colour");

const formOf = (site) => ({
  ...Object.fromEntries(KEYS.map((key) => [key, site[key] ?? ""])),
  links: Object.entries(site.social_links || {}),
});

function SettingsForm({ site }) {
  const save = useSaveSettings();
  const [form, setForm] = useState(() => formOf(site));
  const [saved, setSaved] = useState(false);
  const set = (patch) => {
    setSaved(false);
    setForm((f) => ({ ...f, ...patch }));
  };
  const field = (key) => (e) => set({ [key]: e.target.value });
  const lines = SITE_LINES;
  const setLink = (i, at, value) => set({ links: form.links.map((pair, j) => (j === i ? pair.map((v, k) => (k === at ? value : v)) : pair)) });

  const submit = () => {
    const { links, ...all } = form;
    save.mutate(
      {
        ...Object.fromEntries(Object.entries(all).map(([key, value]) => [key, MPESA.includes(key) ? value.trim() : value])),
        social_links: Object.fromEntries(links.map(([name, url]) => [name.trim(), url.trim()]).filter(([name]) => name)),
      },
      { onSuccess: () => setSaved(true) },
    );
  };

  return (
    <Card variant="outline">
      <CardTitle>Site settings</CardTitle>
      <div className="grid gap-3 sm:grid-cols-2">
        <ConfigFields fields={lines.filter(([key]) => !MPESA.includes(key))} form={form} set={field} />
        <ColourFields form={form} set={(key) => (value) => set({ [key]: value })} />
      </div>
      <ConfigFields fields={SITE_TEXTS} form={form} set={field} />
      <div className="flex flex-col gap-2">
        <div className="grid gap-3 sm:grid-cols-3">
          <ConfigFields fields={lines.filter(([key]) => MPESA.includes(key))} form={form} set={field} />
        </div>
        <Help>The Contribute page offers these to pay by code. Give a Paybill or a Till, not both.</Help>
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-body font-bold">Social links</h3>
        {form.links.map(([name, url], i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <Input className="w-full sm:w-44" aria-label={`Social link ${i + 1} name`} value={name} onChange={(e) => setLink(i, 0, e.target.value)} placeholder="facebook" />
            <Input className="w-full sm:w-auto sm:min-w-56 sm:flex-1" aria-label={`Social link ${i + 1} address`} value={url} onChange={(e) => setLink(i, 1, e.target.value)} placeholder="https://" />
            <Button size="sm" variant="quiet" onClick={() => set({ links: form.links.filter((_, j) => j !== i) })}>Remove</Button>
          </div>
        ))}
        <div>
          <Button size="sm" variant="quiet" onClick={() => set({ links: [...form.links, ["", ""]] })}>Add a link</Button>
        </div>
      </div>
      <ErrorText error={save.error} className="text-ui" />
      {saved && <StatusText>Saved.</StatusText>}
      <div className="flex flex-wrap gap-2">
        <Button loading={save.isPending} size="sm" disabled={save.isPending} onClick={submit}>
          {save.isPending ? "Saving…" : "Save the site settings"}
        </Button>
      </div>
    </Card>
  );
}

export default function SiteSettings() {
  const site = useSite();
  if (site.isPending) return <LoadingText>Loading the site settings…</LoadingText>;
  if (site.error) return <Failed error={site.error} onRetry={() => site.refetch()} />;
  return <SettingsForm key={site.data.updated_at} site={site.data} />;
}
