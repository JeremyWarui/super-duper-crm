// The workspace's Website page (aspirant installations, site.write): the candidate page the
// homepage shows, and the news, slides, issues, documents and videos. Saves through /workspace/site/.
import { useState } from "react";
import {
  WORKSPACE_SECTIONS,
  useSaveWorkspaceCandidatePage,
  useWorkspaceCandidatePage,
} from "@/api/hooks";
import { FilterPills } from "@/components/ui/tabs";
import { formatDate } from "@/lib/format";
import {
  DOCUMENT_FIELDS,
  ISSUE_FIELDS,
  POST_FIELDS,
  ProfileForm,
  SLIDE_FIELDS,
  SectionList,
  VIDEO_FIELDS,
} from "../party/Website";

const section = (kind, rest) => ({ ...WORKSPACE_SECTIONS[kind], ...rest });

const SECTIONS = {
  News: [
    section("posts", { noun: "post", title: "News and events", fields: POST_FIELDS, name: (r) => r.title, meta: (r) => `${r.kind === "event" ? "Event" : "News"} · ${formatDate(r.kind === "event" ? r.event_date : r.published_on) || "not yet published"}` }),
  ],
  Homepage: [
    section("slides", { noun: "slide", title: "Carousel slides", hint: "Up to 5, rotating every 6 seconds.", fields: SLIDE_FIELDS, name: (r) => r.headline, meta: (r) => `Order ${r.sort_order}`, max: 5 }),
    section("issues", { noun: "issue", title: "Agenda issues", hint: "What the campaign stands for, each on its own page.", fields: ISSUE_FIELDS, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` }),
  ],
  Media: [
    section("videos", { noun: "video", title: "Videos", fields: VIDEO_FIELDS, name: (r) => r.title, meta: (r) => [r.duration, `order ${r.sort_order}`].filter(Boolean).join(" · ") }),
    section("documents", { noun: "document", title: "Documents", fields: DOCUMENT_FIELDS, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` }),
  ],
};

const TABS = ["Candidate page", ...Object.keys(SECTIONS)];

function CandidatePage({ campaign }) {
  const page = useWorkspaceCandidatePage();
  const save = useSaveWorkspaceCandidatePage();
  if (page.isLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (page.error) return <p role="alert" className="text-destructive">{page.error.message}</p>;
  return (
    <div className="flex max-w-[720px] flex-col gap-3">
      <ProfileForm key={page.dataUpdatedAt} title={`${campaign.candidate_name || campaign.title}: the homepage`} profile={page.data} save={save} />
      {save.isSuccess ? <p role="status" className="text-small text-muted-foreground">Saved.</p> : null}
    </div>
  );
}

export default function Website({ campaign }) {
  const [tab, setTab] = useState(TABS[0]);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-display text-h2-app font-extrabold tracking-[-0.02em]">Website</h1>
        <p className="text-ui text-muted-foreground">What the public site shows. Changes go live when published.</p>
      </div>
      <FilterPills label="Website content" options={TABS} value={tab} onChange={setTab} />
      {tab === "Candidate page" ? <CandidatePage campaign={campaign} /> : SECTIONS[tab].map((s) => <SectionList key={s.noun} section={s} />)}
    </div>
  );
}
