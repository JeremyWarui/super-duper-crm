// Put an event on the public website, with what it shows there: a description and a photo.
import { useState } from "react";
import { useSetEventWebsite } from "@/api/hooks";
import { ImageField } from "@/components/SiteEditor";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Check, Field, Textarea } from "@/components/ui/input";

export default function WebsiteEventForm({ event, onClose }) {
  const save = useSetEventWebsite();
  const [form, setForm] = useState({ published: event.published, description: event.description || "", image_url: event.image_url || "" });
  const submit = () => save.mutate({ id: event.id, ...form }, { onSuccess: onClose });
  return (
    <Dialog title="Event on the website" description={`${event.title} · ${event.ward_name}`} onClose={onClose}>
      <Check checked={form.published} onChange={(e) => setForm({ ...form, published: e.target.checked })}>
        <span className="flex flex-col"><span className="font-semibold">Show on the website</span><span className="text-small text-muted-foreground">Listed under Events until the day passes, with a link to register while sign-ups are open.</span></span>
      </Check>
      <Field label="Description (optional)">
        <Textarea rows={4} maxLength={2000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What happens, who should come, what to bring." />
      </Field>
      <ImageField label="Photo (optional)" value={form.image_url} upload="/workspace/site/images/" area="site" onChange={(image_url) => setForm({ ...form, image_url })} />
      <ErrorText error={save.isError && save.error} />
      <FormActions>
        <Button variant="quiet" onClick={onClose}>Cancel</Button>
        <Button loading={save.isPending} disabled={save.isPending} onClick={submit}>Save</Button>
      </FormActions>
    </Dialog>
  );
}
