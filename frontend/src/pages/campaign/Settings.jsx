// The workspace's Settings page (aspirant installations, site.write): the website's name, colours,
// contacts, how to give and the privacy notice. The whole row is sent back on save.
import { useSaveWorkspaceSettings, useWorkspaceSettings } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import ConfigFields from "@/components/ConfigFields";
import { ColourFields } from "@/components/Swatch";
import { SITE_LINES, SITE_TEXTS, only } from "@/lib/siteFields";
import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";
import { useForm } from "@/lib/form";
import { SlottedHeader } from "@/components/layout/AppPage";

const LINES = only(SITE_LINES, [
  "name", "short_name", "logo_url", "contact_email", "contact_phone", "address", "privacy_notice_version",
  "mpesa_paybill", "mpesa_account", "mpesa_till",
]);
const TEXTS = only(SITE_TEXTS, ["description", "payment_instructions", "privacy_notice"]);
const COLOURS = ["primary_colour", "secondary_colour"];
// Sent back unchanged; this page does not edit them.
const KEPT = ["about_headline", "social_links", "manifesto_text", "manifesto_url"];

function SettingsForm({ settings }) {
  const save = useSaveWorkspaceSettings();
  const [form, setForm, set] = useForm(settings);
  const submit = (e) => {
    e.preventDefault();
    const body = Object.fromEntries(
      [...LINES.map(([k]) => k), ...COLOURS, ...TEXTS.map(([k]) => k), ...KEPT].map((k) => [k, form[k] ?? ""]),
    );
    save.mutate({ ...body, social_links: form.social_links || {} });
  };
  return (
    <Card variant="outline" asChild>
      <form onSubmit={submit} className="flex max-w-[720px] flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <ConfigFields fields={LINES} form={form} set={set} />
          <ColourFields form={form} set={(key) => (value) => setForm((f) => ({ ...f, [key]: value }))} />
        </div>
        <ConfigFields fields={TEXTS} form={form} set={set} />
        <ErrorText error={save.error} className="text-small" />
        {save.isSuccess ? <p role="status" className="text-small text-muted-foreground">Saved.</p> : null}
        <Button type="submit" className="self-start" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save settings"}</Button>
      </form>
    </Card>
  );
}

export default function Settings() {
  const settings = useWorkspaceSettings();
  return (
    <div className="flex flex-col gap-6">
      <SlottedHeader title="Settings" sub="The website's name, colours and contacts." />
      {settings.isLoading ? <LoadingText /> : null}
      <ErrorText error={settings.error} />
      {settings.data ? <SettingsForm key={settings.data.updated_at} settings={settings.data} /> : null}
    </div>
  );
}
