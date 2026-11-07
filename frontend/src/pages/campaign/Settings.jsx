// The workspace's Settings page (aspirant installations, site.write): the website's name, colours,
// contacts, how to give and the privacy notice. The whole row is sent back on save.
import { useState } from "react";
import { useSaveWorkspaceSettings, useWorkspaceSettings } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/input";
import { ErrorText } from "@/components/ui/error-text";

const LINES = [
  ["name", "Site name", 150],
  ["short_name", "Short name (3 letters or fewer go on the logo tile)", 30],
  ["logo_url", "Logo address (https://)", 500],
  ["contact_email", "Contact email", 254],
  ["contact_phone", "Contact phone", 20],
  ["address", "Address", 300],
  ["privacy_notice_version", "Privacy notice version", 20],
  ["mpesa_paybill", "M-Pesa Paybill number (leave blank for a Till)", 7],
  ["mpesa_account", "Paybill account number", 20],
  ["mpesa_till", "M-Pesa Till number (leave blank for a Paybill)", 7],
];
const COLOURS = [
  ["primary_colour", "Primary colour", "Buttons and links; white text sits on it."],
  ["secondary_colour", "Secondary colour", "Highlights; dark text sits on it."],
];
const TEXTS = [
  ["description", "About the campaign", 6],
  ["payment_instructions", "How to give (shown on the Contribute page)", 4],
  ["privacy_notice", "Privacy notice", 8],
];
// Sent back unchanged; this page does not edit them.
const KEPT = ["about_headline", "social_links", "manifesto_text", "manifesto_url"];

function SettingsForm({ settings }) {
  const save = useSaveWorkspaceSettings();
  const [form, setForm] = useState(settings);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const submit = (e) => {
    e.preventDefault();
    const body = Object.fromEntries(
      [...LINES.map(([k]) => k), ...COLOURS.map(([k]) => k), ...TEXTS.map(([k]) => k), ...KEPT].map((k) => [k, form[k] ?? ""]),
    );
    save.mutate({ ...body, social_links: form.social_links || {} });
  };
  return (
    <Card variant="outline" asChild>
      <form onSubmit={submit} className="flex max-w-[720px] flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {LINES.map(([key, label, max]) => (
            <Field key={key} label={label}><Input value={form[key] ?? ""} maxLength={max} onChange={set(key)} /></Field>
          ))}
          {COLOURS.map(([key, label, hint]) => (
            <Field key={key} label={label} hint={hint}>
              <span className="flex items-center gap-2">
                <span aria-hidden className="size-8 shrink-0 rounded-md border border-line" style={{ background: form[key] }} />
                <Input value={form[key] ?? ""} maxLength={7} onChange={set(key)} placeholder="#0B5D3B" />
              </span>
            </Field>
          ))}
        </div>
        {TEXTS.map(([key, label, rows]) => (
          <Field key={key} label={label}><Textarea rows={rows} value={form[key] ?? ""} onChange={set(key)} /></Field>
        ))}
        <ErrorText error={save.error} className="text-small" />
        {save.isSuccess ? <p role="status" className="text-small text-muted-foreground">Saved.</p> : null}
        <Button type="submit" shape="rounded" className="self-start" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save settings"}</Button>
      </form>
    </Card>
  );
}

export default function Settings() {
  const settings = useWorkspaceSettings();
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-display text-h2-app font-extrabold tracking-[-0.02em]">Settings</h1>
        <p className="text-ui text-muted-foreground">The website's name, colours and contacts.</p>
      </div>
      {settings.isLoading ? <p className="text-muted-foreground">Loading…</p> : null}
      <ErrorText error={settings.error} />
      {settings.data ? <SettingsForm key={settings.data.updated_at} settings={settings.data} /> : null}
    </div>
  );
}
