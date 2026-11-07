// The superuser's editor for the public site: slides, issues, posts, leaders, candidates, About content and results.
// Its lists, item form and profile form also serve an aspirant installation's workspace Website page.
import { useId, useRef, useState } from "react";
import { ImageUp } from "lucide-react";
import {
  usePostAspirants,
  useSaveProfile,
  useSavePostAspirants,
  useSiteCandidates,
  useDeleteDocument,
  useDeleteIssue,
  useDeleteLeader,
  useDeleteOrgan,
  useDeletePost,
  useDeleteResult,
  useDeleteSlide,
  useDeleteValue,
  useDeleteVideo,
  useSaveDocument,
  useSaveIssue,
  useSaveLeader,
  useSaveOrgan,
  useSavePost,
  useSaveResult,
  useSaveSlide,
  useSaveValue,
  useSaveVideo,
  usePartyPlaces,
  useSiteDocuments,
  useSiteIssues,
  useSiteLeaders,
  useSiteOrgans,
  useSitePosts,
  useSiteResults,
  useSiteSlides,
  useSiteValues,
  useSiteVideos,
  useUploadImage,
} from "@/api/hooks";
import { RichTextEditor } from "@/components/RichText";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, NativeSelect, Textarea } from "@/components/ui/input";
import { FilterPills } from "@/components/ui/tabs";
import { formatDate } from "@/lib/format";
import { SEAT_LABEL, SEATS } from "./helpers";
import { ErrorText } from "@/components/ui/error-text";

const HTTPS = /^https:\/\/\S+$/;
const UPLOADED = /^\/api\/files\/[0-9a-f-]{36}\/$/;
const imageOk = (v) => !v || HTTPS.test(v) || UPLOADED.test(v);
const IMAGE_HINT = "A JPEG, PNG or WebP up to 5 MB, or an https:// address.";
const PDF_HINT = "A PDF up to 10 MB, or an https:// address.";
const CHECKS = {
  image: (v) => imageOk(v) || "Choose a file, or use an address starting with https://.",
  pdf: (v) => imageOk(v) || "Choose a PDF, or use an address starting with https://.",
  https: (v) => !v || HTTPS.test(v) || "Use an address starting with https://.",
  link: (v, f) => !v || HTTPS.test(v) || (/^\/(?!\/)\S*$/.test(v)) || `Use a page on this site such as ${f.example || "/join-party"}, or an https:// address.`,
  order: (v) => (/^\d{1,5}$/.test(v) && Number(v) <= 10000) || "Use a whole number from 0 to 10000.",
  duration: (v) => !v || /^(\d{1,2}:)?\d{1,2}:\d{2}$/.test(v) || "Use minutes and seconds, such as 4:15.",
  count: (v) => /^\d{1,8}$/.test(v) && Number(v) <= 10000000 || "Use a whole number of votes.",
};
const ORDER = { key: "sort_order", label: "Order", kind: "order", hint: "Lower numbers come first." };

export const SLIDE_FIELDS = [
  { key: "headline", label: "Headline", max: 120, required: true },
  { key: "kicker", label: "Kicker (optional)", max: 80, hint: "The small line above the headline." },
  { key: "line", label: "Supporting text (optional)", max: 300, kind: "area" },
  { key: "button_label", label: "Button label (optional)", max: 40 },
  { key: "button_url", label: "Button link (optional)", max: 500, kind: "link", hint: "A page on this site such as /counties, or an https:// address." },
  { key: "image_url", label: "Photo (optional)", max: 500, kind: "image", area: "slides" },
  ORDER,
];

export const ISSUE_FIELDS = [
  { key: "title", label: "Title", max: 150, required: true },
  { key: "summary", label: "Summary (optional)", max: 300, kind: "area" },
  { key: "what_we_will_do", label: "What we will do (optional)", max: 20000, kind: "area", hint: "One step per line; each becomes a numbered card." },
  { key: "why_it_matters", label: "Why it matters (optional)", max: 20000, kind: "area" },
  ORDER,
];

const LEADER_FIELDS = [
  { key: "name", label: "Name", max: 150, required: true },
  { key: "position", label: "Position", max: 150, required: true },
  { key: "bio", label: "Bio (optional)", kind: "rich", area: "leaders" },
  { key: "photo_url", label: "Photo (optional)", max: 500, kind: "image", area: "leaders" },
  ORDER,
];

const isEvent = (form) => form.kind === "event";
const isNews = (form) => form.kind !== "event";
const isStatement = (form) => isNews(form) && form.label === "statement";
export const POST_FIELDS = [
  { key: "kind", label: "Kind", kind: "select", options: [["news", "News"], ["event", "Event"]], newOnly: true },
  { key: "label", label: "Label", kind: "select", options: [["news", "News"], ["statement", "Statement"], ["opinion", "Opinion"]], show: isNews },
  { key: "title", label: "Title", max: 150, required: true },
  { key: "event_date", label: "Date", kind: "date", required: true, show: isEvent },
  { key: "venue", label: "Venue (optional)", max: 150, show: isEvent },
  { key: "county_id", label: "County (optional)", kind: "county", show: isEvent },
  { key: "place", label: "Place (optional)", max: 80, show: isNews, hint: "Shown beside the label, such as National or Nakuru." },
  { key: "author", label: "Author (optional)", max: 150, show: isNews, hint: "For a statement, who issued it, such as Grace Chebet, Secretary General." },
  { key: "author_photo_url", label: "Author photo (optional)", max: 500, kind: "image", area: "site", show: isNews },
  { key: "reference", label: "Reference (optional)", max: 40, show: isStatement },
  { key: "pdf_url", label: "Signed PDF (optional)", kind: "pdf", area: "documents", show: isStatement, hint: "A PDF up to 10 MB, or an https:// address. Readers see it on the statement page." },
  { key: "body", label: "Text", kind: "rich", area: "site" },
  { key: "image_url", label: "Image (optional)", max: 500, kind: "image", area: "site" },
];

const ABOUT_FIELDS = [
  { key: "title", label: "Title", max: 150, required: true },
  { key: "text", label: "Text (optional)", max: 300, kind: "area" },
  ORDER,
];

export const DOCUMENT_FIELDS = [
  { key: "title", label: "Title", max: 150, required: true, hint: "Such as Party constitution (PDF)." },
  { key: "url", label: "Address", max: 500, kind: "https", required: true },
  ORDER,
];

export const VIDEO_FIELDS = [
  { key: "title", label: "Title", max: 150, required: true },
  { key: "url", label: "Video address", max: 500, kind: "https", required: true, hint: "Such as a YouTube link; the card opens it." },
  { key: "thumbnail_url", label: "Thumbnail (optional)", max: 500, kind: "image", area: "site", hint: "Left empty, a YouTube link shows YouTube's thumbnail." },
  { key: "duration", label: "Length (optional)", max: 8, kind: "duration", hint: "Such as 4:15 or 1:02:30." },
  ORDER,
];

const RESULT_FIELDS = [
  { key: "seat", label: "Seat", kind: "select", options: SEATS.map(([value, label]) => [value, label]) },
  { key: "area", label: "Area", max: 150, required: true, hint: "The ward, constituency or county, such as Westlands." },
  { key: "candidate", label: "Candidate", max: 150, required: true },
  { key: "votes", label: "Votes", kind: "count", required: true },
  { key: "declared_on", label: "Declared on (optional)", kind: "date", hint: "Leave empty while the count goes on." },
];

const PARTY_UPLOAD = "/files/";
const SECTIONS = {
  Homepage: [
    { noun: "slide", upload: PARTY_UPLOAD, title: "Carousel slides", hint: "Up to 5, rotating every 6 seconds.", fields: SLIDE_FIELDS, query: useSiteSlides, save: useSaveSlide, del: useDeleteSlide, name: (r) => r.headline, meta: (r) => `Order ${r.sort_order}`, max: 5 },
    { noun: "issue", title: "Agenda issues", hint: "Each opens its own page from the homepage.", fields: ISSUE_FIELDS, query: useSiteIssues, save: useSaveIssue, del: useDeleteIssue, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` },
    { noun: "video", upload: PARTY_UPLOAD, title: "Watch videos", hint: "The first three show under News on the homepage.", fields: VIDEO_FIELDS, query: useSiteVideos, save: useSaveVideo, del: useDeleteVideo, name: (r) => r.title, meta: (r) => [r.duration, `order ${r.sort_order}`].filter(Boolean).join(" · ") },
  ],
  Posts: [
    { noun: "post", upload: PARTY_UPLOAD, title: "News and events", aspirants: true, fields: POST_FIELDS, query: useSitePosts, save: useSavePost, del: useDeletePost, name: (r) => r.title, meta: (r) => `${r.kind === "event" ? "Event" : "News"} · ${formatDate(r.kind === "event" ? r.event_date : r.published_on) || "not yet published"}` },
  ],
  Leaders: [
    { noun: "leader", upload: PARTY_UPLOAD, title: "Party leaders", fields: LEADER_FIELDS, query: useSiteLeaders, save: useSaveLeader, del: useDeleteLeader, name: (r) => r.name, meta: (r) => `${r.position} · order ${r.sort_order}` },
  ],
  About: [
    { noun: "value", title: "What we believe", hint: "The party's values on the About page.", fields: ABOUT_FIELDS, query: useSiteValues, save: useSaveValue, del: useDeleteValue, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` },
    { noun: "organ", title: "How the party is run", hint: "The party's organs and what each does.", fields: ABOUT_FIELDS, query: useSiteOrgans, save: useSaveOrgan, del: useDeleteOrgan, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` },
    { noun: "document", title: "Party documents", hint: "Linked from the About page.", fields: DOCUMENT_FIELDS, query: useSiteDocuments, save: useSaveDocument, del: useDeleteDocument, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` },
  ],
  Results: [
    { noun: "result", title: "Primary results", hint: "One row per candidate; rows with the same seat and area form one race.", fields: RESULT_FIELDS, query: useSiteResults, save: useSaveResult, del: useDeleteResult, name: (r) => `${r.candidate}, ${SEAT_LABEL[r.seat]} ${r.area}`, meta: (r) => `${r.votes.toLocaleString("en-KE")} votes · ${r.declared_on ? `declared ${formatDate(r.declared_on)}` : "counting"}${r.demo ? " · demo" : ""}` },
  ],
};

const blank = (fields) => Object.fromEntries(fields.map((f) => [f.key, f.kind === "order" || f.kind === "count" ? "0" : f.kind === "select" ? f.options[0][0] : ""]));
const formOf = (fields, row) => (row ? Object.fromEntries(fields.map((f) => [f.key, row[f.key] == null ? "" : String(row[f.key])])) : blank(fields));

function problems(fields, form) {
  const out = {};
  for (const f of fields) {
    if (f.show && !f.show(form)) continue;
    const v = form[f.key].trim();
    if (f.required && !v) out[f.key] = `${f.label} is needed.`;
    else if (CHECKS[f.kind]) {
      const ok = CHECKS[f.kind](v, f);
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
    body[f.key] = f.kind === "order" || f.kind === "count" ? Number(v) : f.kind === "county" || (f.kind === "date" && !f.required) ? v || null : v;
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

/** An image address with a file picker that uploads the chosen image and fills the address in. */
/** An uploaded file or an https:// address; `pdf` takes a PDF instead of an image. */
export function ImageField({ label, hint, value, onChange, invalid, upload: path, area, pdf = false }) {
  const id = useId();
  const picker = useRef(null);
  const send = useUploadImage(path);
  const pick = (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) send.mutate({ file, area }, { onSuccess: (stored) => onChange(stored.url) });
  };
  const note = send.error?.message || hint || (pdf ? PDF_HINT : IMAGE_HINT);
  return (
    <div className="flex flex-col gap-1.5 text-small font-semibold">
      <label htmlFor={id}>{label}</label>
      <div className="flex flex-wrap items-center gap-2">
        {!pdf && value && imageOk(value) ? <img src={value} alt="" className="size-11 flex-none rounded-lg border border-line object-cover" /> : null}
        <Input id={id} className="min-w-0 flex-[1_1_200px]" value={value} maxLength={500} placeholder="https://" aria-invalid={invalid} onChange={(e) => onChange(e.target.value)} />
        <input ref={picker} type="file" accept={pdf ? "application/pdf" : "image/jpeg,image/png,image/webp"} className="sr-only" tabIndex={-1} aria-label={`Choose a file for ${label}`} onChange={pick} />
        <Button type="button" shape="rounded" variant="quiet" disabled={send.isPending || !path} onClick={() => picker.current?.click()}>
          <ImageUp size={18} aria-hidden />{send.isPending ? "Uploading…" : "Choose file"}
        </Button>
      </div>
      <span role={send.error ? "alert" : undefined} className={send.error ? "font-semibold text-destructive" : "font-normal text-muted-foreground"}>{note}</span>
    </div>
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
          if (f.kind === "rich") {
            return <RichTextEditor key={f.key} label={f.label} hint={hint} value={form[f.key]} upload={section.upload} area={f.area} onChange={(v) => setForm((now) => ({ ...now, [f.key]: v }))} />;
          }
          if (f.kind === "image" || f.kind === "pdf") {
            return <ImageField key={f.key} pdf={f.kind === "pdf"} label={f.label} hint={hint} value={form[f.key]} invalid={common["aria-invalid"]} upload={section.upload} area={f.area} onChange={(v) => setForm((now) => ({ ...now, [f.key]: v }))} />;
          }
          return (
            <Field key={f.key} label={f.label} hint={hint}>
              {f.kind === "area" ? <Textarea rows={4} maxLength={f.max} {...common} />
                : f.kind === "select" ? <NativeSelect {...common}>{f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</NativeSelect>
                : f.kind === "county" ? <CountySelect {...common} />
                : <Input type={f.kind === "date" ? "date" : "text"} inputMode={f.kind === "order" || f.kind === "count" ? "numeric" : undefined} maxLength={f.max} {...common} />}
            </Field>
          );
        })}
        <ErrorText error={save.error} className="text-small" />
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
      <ErrorText error={del.error} className="text-small" />
      <div className="flex justify-end gap-2.5">
        <Button shape="rounded" variant="quiet" onClick={onClose}>Cancel</Button>
        <Button shape="rounded" variant="danger" disabled={del.isPending} onClick={() => del.mutate(row.id, { onSuccess: onClose })}>Delete</Button>
      </div>
    </Dialog>
  );
}

export function SectionList({ section }) {
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
        <ErrorText error={rows.error} />
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
        <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-6">
          <ItemForm key={editing.row?.id || "new"} section={section} row={editing.row} onDone={() => setEditing(null)} />
          {section.aspirants && editing.row?.kind === "event" ? <EventAspirants key={`aspirants-${editing.row.id}`} postId={editing.row.id} /> : null}
        </div>
      ) : null}
      {deleting ? <ConfirmDelete section={section} row={deleting} onClose={() => setDeleting(null)} /> : null}
    </div>
  );
}

/** The approved aspirants an event names; each one's profile lists the event. */
function EventAspirants({ postId }) {
  const named = usePostAspirants(postId);
  const aspirants = useSiteCandidates().data || [];
  const save = useSavePostAspirants();
  const [picked, setPicked] = useState(null);
  const chosen = picked ?? named.data?.aspirant_ids ?? [];
  const toggle = (id) => setPicked(chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id]);
  return (
    <Card variant="outline" className="gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="text-card-title font-bold">Aspirants at this event</h2>
        <p className="text-small text-muted-foreground">The event shows on each one's candidate profile.</p>
      </div>
      {aspirants.length ? (
        <div className="flex flex-col gap-1">
          {aspirants.map((a) => (
            <label key={a.aspirant_id} className="flex min-h-11 items-center gap-3">
              <input type="checkbox" className="size-[18px] accent-primary" checked={chosen.includes(a.aspirant_id)} onChange={() => toggle(a.aspirant_id)} />
              <span>{a.name} <span className="text-small text-muted-foreground">· {SEAT_LABEL[a.seat]} {a.area}</span></span>
            </label>
          ))}
        </div>
      ) : <p className="text-muted-foreground">No approved aspirants yet.</p>}
      <ErrorText error={save.error} className="text-small" />
      {save.isSuccess && picked === null ? <p role="status" className="text-small text-muted-foreground">Saved.</p> : null}
      <Button shape="rounded" className="self-start" disabled={picked === null || save.isPending} onClick={() => save.mutate({ id: postId, aspirant_ids: chosen }, { onSuccess: () => setPicked(null) })}>Save aspirants</Button>
    </Card>
  );
}

const PROFILE_FIELDS = [
  ["slogan", "Slogan (optional)", 120],
  ["office_address", "Campaign office address (optional)", 300],
  ["office_phone", "Campaign office phone (optional)", 20],
  ["office_email", "Campaign office email (optional)", 254],
];
const NO_PRIORITY = { title: "", text: "" };

/** A candidate page's fields; `save` is the mutation that stores them, sent `extra` as well. */
export function ProfileForm({ title, profile: p, save, upload, extra = {}, onDone }) {
  const [form, setForm] = useState({ ...p, priorities: [0, 1, 2].map((n) => p.priorities[n] || NO_PRIORITY) });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const setPriority = (n, key) => (e) => setForm({ ...form, priorities: form.priorities.map((x, i) => (i === n ? { ...x, [key]: e.target.value } : x)) });
  const photoBad = !imageOk(form.photo_url.trim());
  const submit = (e) => {
    e.preventDefault();
    if (photoBad) return;
    const body = { photo_url: form.photo_url.trim(), ...Object.fromEntries(PROFILE_FIELDS.map(([key]) => [key, form[key].trim()])) };
    const priorities = form.priorities.map((x) => ({ title: x.title.trim(), text: x.text.trim() })).filter((x) => x.title);
    save.mutate({ ...extra, ...body, bio: form.bio, published: form.published, priorities }, { onSuccess: onDone });
  };
  return (
    <Card variant="outline" asChild>
      <form onSubmit={submit} noValidate>
        <h2 className="text-card-title font-bold">{title}</h2>
        <ImageField label="Photo (optional)" value={form.photo_url} upload={upload} area="candidates" invalid={photoBad || undefined}
          hint={photoBad ? "Choose a file, or use an address starting with https://." : undefined} onChange={(v) => setForm((now) => ({ ...now, photo_url: v }))} />
        {PROFILE_FIELDS.map(([key, label, max]) => (
          <Field key={key} label={label}>
            <Input value={form[key]} maxLength={max} onChange={set(key)} />
          </Field>
        ))}
        <RichTextEditor label="Biography (optional)" value={form.bio} upload={upload} area="candidates" onChange={(v) => setForm((now) => ({ ...now, bio: v }))} />
        {form.priorities.map((x, n) => (
          <div key={n} className="grid gap-2 sm:grid-cols-[1fr_2fr]">
            <Field label={`Priority ${n + 1} (optional)`}><Input value={x.title} maxLength={80} onChange={setPriority(n, "title")} /></Field>
            <Field label={`Priority ${n + 1} detail (optional)`}><Input value={x.text} maxLength={300} onChange={setPriority(n, "text")} /></Field>
          </div>
        ))}
        <label className="flex min-h-11 items-center gap-3 font-semibold">
          <input type="checkbox" className="size-[18px] accent-primary" checked={form.published} onChange={(e) => setForm({ ...form, published: e.target.checked })} />
          Published on the website
        </label>
        <ErrorText error={save.error} className="text-small" />
        <div className="flex flex-wrap gap-2.5">
          <Button type="submit" shape="rounded" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save profile"}</Button>
          {onDone ? <Button type="button" shape="rounded" variant="quiet" onClick={onDone}>Cancel</Button> : null}
        </div>
      </form>
    </Card>
  );
}

function CandidatesEditor() {
  const list = useSiteCandidates();
  const saveProfile = useSaveProfile();
  const [editing, setEditing] = useState(null);
  const rows = list.data || [];
  return (
    <div className="flex flex-wrap items-start gap-6">
      <Card variant="outline" className="min-w-0 flex-[1_1_420px] gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-card-title font-bold">Candidate profiles</h2>
          <p className="text-small text-muted-foreground">Every approved aspirant. Write the profile from what the candidate sends, then publish it.</p>
        </div>
        {list.isLoading ? <p className="text-muted-foreground">Loading…</p> : null}
        <ErrorText error={list.error} />
        {list.isSuccess && !rows.length ? <p className="text-muted-foreground">No approved aspirants yet.</p> : null}
        <ul className="flex flex-col">
          {rows.map((c) => (
            <li key={c.aspirant_id} className="flex flex-wrap items-center justify-between gap-3 border-t border-line-soft py-3">
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="font-bold">{c.name}</span>
                <span className="text-small text-muted-foreground">{SEAT_LABEL[c.seat]} · {c.area}</span>
              </span>
              <span className="flex items-center gap-2">
                <Badge tone={c.profile.published ? "ok" : "info"}>{c.profile.published ? "Published" : "Draft"}</Badge>
                <Button shape="rounded" variant="quiet" onClick={() => setEditing(c)}>Edit profile</Button>
              </span>
            </li>
          ))}
        </ul>
      </Card>
      {editing ? (
        <div className="min-w-0 flex-[1_1_420px]">
          <ProfileForm key={editing.aspirant_id} title={`Profile of ${editing.name}`} profile={editing.profile} save={saveProfile} upload={PARTY_UPLOAD} extra={{ aspirant_id: editing.aspirant_id }} onDone={() => setEditing(null)} />
        </div>
      ) : null}
    </div>
  );
}

const TABS = [...Object.keys(SECTIONS).slice(0, 3), "Candidates", ...Object.keys(SECTIONS).slice(3)];

export default function Website() {
  const [tab, setTab] = useState("Posts");
  return (
    <div className="flex flex-col gap-6">
      <FilterPills label="Website content" options={TABS} value={tab} onChange={setTab} />
      {tab === "Candidates" ? <CandidatesEditor /> : SECTIONS[tab].map((section) => <SectionList key={section.noun} section={section} />)}
    </div>
  );
}
