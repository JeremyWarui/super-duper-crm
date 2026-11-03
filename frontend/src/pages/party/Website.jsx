// The superuser's editor for the public site: carousel slides, agenda issues, posts, leaders and documents.
import { useState } from "react";
import {
  useDeleteDocument,
  useDeleteIssue,
  useDeleteLeader,
  useDeleteOrgan,
  useDeletePost,
  useDeleteSlide,
  useDeleteValue,
  useSaveDocument,
  useSaveIssue,
  useSaveLeader,
  useSaveOrgan,
  useSavePost,
  useSaveSlide,
  useSaveValue,
  usePartyPlaces,
  useSiteDocuments,
  useSiteIssues,
  useSiteLeaders,
  useSiteOrgans,
  useSitePosts,
  useSiteSlides,
  useSiteValues,
} from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, NativeSelect, Textarea } from "@/components/ui/input";
import { FilterPills } from "@/components/ui/tabs";
import { formatDate } from "@/lib/format";

const HTTPS = /^https:\/\/\S+$/;
const CHECKS = {
  image: (v) => !v || HTTPS.test(v) || "Use an address starting with https://.",
  https: (v) => !v || HTTPS.test(v) || "Use an address starting with https://.",
  link: (v) => !v || HTTPS.test(v) || (/^\/(?!\/)\S*$/.test(v)) || "Use a page on this site such as /join-party, or an https:// address.",
  order: (v) => (/^\d{1,5}$/.test(v) && Number(v) <= 10000) || "Use a whole number from 0 to 10000.",
};
const ORDER = { key: "sort_order", label: "Order", kind: "order", hint: "Lower numbers come first." };

const SLIDE_FIELDS = [
  { key: "headline", label: "Headline", max: 120, required: true },
  { key: "kicker", label: "Kicker (optional)", max: 80, hint: "The small line above the headline." },
  { key: "line", label: "Supporting text (optional)", max: 300, kind: "area" },
  { key: "button_label", label: "Button label (optional)", max: 40 },
  { key: "button_url", label: "Button link (optional)", max: 500, kind: "link", hint: "A page on this site such as /counties, or an https:// address." },
  { key: "image_url", label: "Photo address (optional)", max: 500, kind: "image" },
  ORDER,
];

const ISSUE_FIELDS = [
  { key: "title", label: "Title", max: 150, required: true },
  { key: "summary", label: "Summary (optional)", max: 300, kind: "area" },
  { key: "what_we_will_do", label: "What we will do (optional)", max: 20000, kind: "area", hint: "One step per line; each becomes a numbered card." },
  { key: "why_it_matters", label: "Why it matters (optional)", max: 20000, kind: "area" },
  ORDER,
];

const LEADER_FIELDS = [
  { key: "name", label: "Name", max: 150, required: true },
  { key: "position", label: "Position", max: 150, required: true },
  { key: "bio", label: "Bio (optional)", max: 20000, kind: "area" },
  { key: "photo_url", label: "Photo address (optional)", max: 500, kind: "image" },
  ORDER,
];

const isEvent = (form) => form.kind === "event";
const isNews = (form) => form.kind !== "event";
const isStatement = (form) => isNews(form) && form.label === "statement";
const POST_FIELDS = [
  { key: "kind", label: "Kind", kind: "select", options: [["news", "News"], ["event", "Event"]], newOnly: true },
  { key: "label", label: "Label", kind: "select", options: [["news", "News"], ["statement", "Statement"], ["opinion", "Opinion"]], show: isNews },
  { key: "title", label: "Title", max: 150, required: true },
  { key: "event_date", label: "Date", kind: "date", required: true, show: isEvent },
  { key: "venue", label: "Venue (optional)", max: 150, show: isEvent },
  { key: "county_id", label: "County (optional)", kind: "county", show: isEvent },
  { key: "place", label: "Place (optional)", max: 80, show: isNews, hint: "Shown beside the label, such as National or Nakuru." },
  { key: "author", label: "Author (optional)", max: 150, show: isNews, hint: "For a statement, who issued it, such as Grace Chebet, Secretary General." },
  { key: "author_photo_url", label: "Author photo address (optional)", max: 500, kind: "image", show: isNews },
  { key: "reference", label: "Reference (optional)", max: 40, show: isStatement },
  { key: "pdf_url", label: "Signed PDF address (optional)", max: 500, kind: "https", show: isStatement },
  { key: "body", label: "Text", max: 20000, kind: "area" },
  { key: "image_url", label: "Image address (optional)", max: 500, kind: "image" },
];

const ABOUT_FIELDS = [
  { key: "title", label: "Title", max: 150, required: true },
  { key: "text", label: "Text (optional)", max: 300, kind: "area" },
  ORDER,
];

const DOCUMENT_FIELDS = [
  { key: "title", label: "Title", max: 150, required: true, hint: "Such as Party constitution (PDF)." },
  { key: "url", label: "Address", max: 500, kind: "https", required: true },
  ORDER,
];

const SECTIONS = {
  Homepage: [
    { noun: "slide", title: "Carousel slides", hint: "Up to 5, rotating every 6 seconds.", fields: SLIDE_FIELDS, query: useSiteSlides, save: useSaveSlide, del: useDeleteSlide, name: (r) => r.headline, meta: (r) => `Order ${r.sort_order}`, max: 5 },
    { noun: "issue", title: "Agenda issues", hint: "Each opens its own page from the homepage.", fields: ISSUE_FIELDS, query: useSiteIssues, save: useSaveIssue, del: useDeleteIssue, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` },
  ],
  Posts: [
    { noun: "post", title: "News and events", fields: POST_FIELDS, query: useSitePosts, save: useSavePost, del: useDeletePost, name: (r) => r.title, meta: (r) => `${r.kind === "event" ? "Event" : "News"} · ${formatDate(r.kind === "event" ? r.event_date : r.published_on) || "not yet published"}` },
  ],
  Leaders: [
    { noun: "leader", title: "Party leaders", fields: LEADER_FIELDS, query: useSiteLeaders, save: useSaveLeader, del: useDeleteLeader, name: (r) => r.name, meta: (r) => `${r.position} · order ${r.sort_order}` },
  ],
  About: [
    { noun: "value", title: "What we believe", hint: "The party's values on the About page.", fields: ABOUT_FIELDS, query: useSiteValues, save: useSaveValue, del: useDeleteValue, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` },
    { noun: "organ", title: "How the party is run", hint: "The party's organs and what each does.", fields: ABOUT_FIELDS, query: useSiteOrgans, save: useSaveOrgan, del: useDeleteOrgan, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` },
    { noun: "document", title: "Party documents", hint: "Linked from the About page.", fields: DOCUMENT_FIELDS, query: useSiteDocuments, save: useSaveDocument, del: useDeleteDocument, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` },
  ],
};

const blank = (fields) => Object.fromEntries(fields.map((f) => [f.key, f.kind === "order" ? "0" : f.kind === "select" ? f.options[0][0] : ""]));
const formOf = (fields, row) => (row ? Object.fromEntries(fields.map((f) => [f.key, row[f.key] == null ? "" : String(row[f.key])])) : blank(fields));

function problems(fields, form) {
  const out = {};
  for (const f of fields) {
    if (f.show && !f.show(form)) continue;
    const v = form[f.key].trim();
    if (f.required && !v) out[f.key] = `${f.label} is needed.`;
    else if (CHECKS[f.kind]) {
      const ok = CHECKS[f.kind](v);
      if (ok !== true) out[f.key] = ok;
    }
  }
  return out;
}

function payload(fields, form, row) {
  const body = {};
  for (const f of fields) {
    if ((f.show && !f.show(form)) || (f.newOnly && row)) continue;
    const v = f.kind === "area" ? form[f.key] : form[f.key].trim();
    body[f.key] = f.kind === "order" ? Number(v) : f.kind === "county" ? v || null : v;
  }
  if (!row) return body;
  return Object.fromEntries(Object.entries(body).filter(([k, v]) => (v ?? "") !== (row[k] ?? "")));
}

function CountySelect(props) {
  const counties = usePartyPlaces().data || [];
  return (
    <NativeSelect {...props}>
      <option value="">No county</option>
      {counties.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
    </NativeSelect>
  );
}

function ItemForm({ section, row, onDone }) {
  const save = section.save();
  const [form, setForm] = useState(() => formOf(section.fields, row));
  const [tried, setTried] = useState(false);
  const errors = problems(section.fields, form);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const submit = (e) => {
    e.preventDefault();
    setTried(true);
    if (Object.keys(errors).length) return;
    const body = payload(section.fields, form, row);
    if (row && !Object.keys(body).length) return onDone();
    save.mutate(row ? { id: row.id, ...body } : body, { onSuccess: onDone });
  };
  const shown = section.fields.filter((f) => (!f.show || f.show(form)) && !(f.newOnly && row));
  return (
    <Card variant="outline" asChild>
      <form onSubmit={submit} noValidate>
        <div className="flex flex-col gap-1">
          <h2 className="text-card-title font-bold">{row ? `Edit ${section.name(row)}` : `New ${section.noun}`}</h2>
          <p className="text-small text-muted-foreground">Saved as a draft until you publish it.</p>
        </div>
        {shown.map((f) => {
          const common = { value: form[f.key], onChange: set(f.key), "aria-invalid": tried && errors[f.key] ? true : undefined };
          const hint = (tried && errors[f.key]) || f.hint;
          return (
            <Field key={f.key} label={f.label} hint={hint}>
              {f.kind === "area" ? <Textarea rows={4} maxLength={f.max} {...common} />
                : f.kind === "select" ? <NativeSelect {...common}>{f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</NativeSelect>
                : f.kind === "county" ? <CountySelect {...common} />
                : <Input type={f.kind === "date" ? "date" : "text"} inputMode={f.kind === "order" ? "numeric" : undefined} maxLength={f.max} {...common} />}
            </Field>
          );
        })}
        {save.error ? <p role="alert" className="text-small font-semibold text-destructive">{save.error.message}</p> : null}
        <div className="flex flex-wrap gap-2.5">
          <Button type="submit" shape="rounded" disabled={save.isPending || (!row && Object.keys(errors).length > 0)}>
            {save.isPending ? "Saving…" : row ? `Save ${section.noun}` : `Add ${section.noun}`}
          </Button>
          <Button type="button" shape="rounded" variant="quiet" onClick={onDone}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

function ConfirmDelete({ section, row, onClose }) {
  const del = section.del();
  return (
    <Dialog title={`Delete ${section.name(row)}?`} description="It leaves the public site at once and cannot be brought back." onClose={onClose}>
      {del.error ? <p role="alert" className="text-small font-semibold text-destructive">{del.error.message}</p> : null}
      <div className="flex justify-end gap-2.5">
        <Button shape="rounded" variant="quiet" onClick={onClose}>Cancel</Button>
        <Button shape="rounded" variant="danger" disabled={del.isPending} onClick={() => del.mutate(row.id, { onSuccess: onClose })}>Delete</Button>
      </div>
    </Dialog>
  );
}

function SectionList({ section }) {
  const rows = section.query();
  const save = section.save();
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const list = rows.data || [];
  const full = section.max && list.length >= section.max;
  return (
    <div className="flex flex-wrap items-start gap-6">
      <Card variant="outline" className="min-w-0 flex-[1_1_420px] gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 className="text-card-title font-bold">{section.title}</h2>
            {section.hint ? <p className="text-small text-muted-foreground">{section.hint}</p> : null}
          </div>
          <Button shape="rounded" disabled={full} onClick={() => setEditing({ row: null })}>New {section.noun}</Button>
        </div>
        {rows.isLoading ? <p className="text-muted-foreground">Loading…</p> : null}
        {rows.error ? <p role="alert" className="text-destructive">{rows.error.message}</p> : null}
        {rows.isSuccess && !list.length ? <p className="text-muted-foreground">Nothing here yet.</p> : null}
        <ul className="flex flex-col">
          {list.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-line-soft py-3">
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="font-bold">{section.name(r)}</span>
                <span className="text-small text-muted-foreground">{section.meta(r)}</span>
              </span>
              <span className="flex flex-wrap items-center gap-2">
                <Badge tone={r.published ? "ok" : "info"}>{r.published ? "Published" : "Draft"}</Badge>
                <Button size="sm" shape="rounded" variant="quiet" onClick={() => setEditing({ row: r })}>Edit</Button>
                <Button size="sm" shape="rounded" variant="quiet" disabled={save.isPending} onClick={() => save.mutate({ id: r.id, published: !r.published })}>
                  {r.published ? "Unpublish" : "Publish"}
                </Button>
                <Button size="sm" shape="rounded" variant="danger" onClick={() => setDeleting(r)}>Delete</Button>
              </span>
            </li>
          ))}
        </ul>
        {full ? <p className="text-small text-muted-foreground">The carousel is full; delete a slide to add another.</p> : null}
      </Card>
      {editing ? (
        <div className="min-w-0 flex-[1_1_420px]">
          <ItemForm key={editing.row?.id || "new"} section={section} row={editing.row} onDone={() => setEditing(null)} />
        </div>
      ) : null}
      {deleting ? <ConfirmDelete section={section} row={deleting} onClose={() => setDeleting(null)} /> : null}
    </div>
  );
}

export default function Website() {
  const [tab, setTab] = useState("Posts");
  return (
    <div className="flex flex-col gap-6">
      <FilterPills label="Website content" options={Object.keys(SECTIONS)} value={tab} onChange={setTab} />
      {SECTIONS[tab].map((section) => <SectionList key={section.noun} section={section} />)}
    </div>
  );
}
