// The superuser's editor for the public site: slides, issues, posts, leaders, candidates, About content and results.
// Its lists, item form and profile form also serve an aspirant installation's workspace Website page.
import { useState } from "react";
import { useSaveProfile, useSiteCandidates, useDeleteDocument, useDeleteIssue, useDeleteLeader, useDeleteOrgan, useDeletePost, useDeleteResult, useDeleteSlide, useDeleteValue, useDeleteVideo, useSaveDocument, useSaveIssue, useSaveLeader, useSaveOrgan, useSavePost, useSaveResult, useSaveSlide, useSaveValue, useSaveVideo, useSiteDocuments, useSiteIssues, useSiteLeaders, useSiteOrgans, useSitePosts, useSiteResults, useSiteSlides, useSiteValues, useSiteVideos } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { FilterPills } from "@/components/ui/tabs";
import { formatDate, formatNumber } from "@/lib/format";
import { SEAT_LABEL } from "@/lib/labels";
import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";

import { ABOUT_FIELDS, DOCUMENT_FIELDS, ISSUE_FIELDS, LEADER_FIELDS, POST_FIELDS, ProfileForm, RESULT_FIELDS, SectionList, SLIDE_FIELDS, VIDEO_FIELDS } from "@/components/SiteEditor";
const PARTY_UPLOAD = "/files/";
const SECTIONS = {
  Homepage: [
    { noun: "slide", upload: PARTY_UPLOAD, title: "Carousel slides", hint: "Up to 5, rotating every 6 seconds.", fields: SLIDE_FIELDS, query: useSiteSlides, save: useSaveSlide, del: useDeleteSlide, name: (r) => r.headline, meta: (r) => `Order ${r.sort_order}`, max: 5 },
    { noun: "issue", upload: PARTY_UPLOAD, title: "Agenda issues", hint: "Each opens its own page from the homepage.", fields: ISSUE_FIELDS, query: useSiteIssues, save: useSaveIssue, del: useDeleteIssue, name: (r) => r.title, meta: (r) => `Order ${r.sort_order}` },
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
    { noun: "result", title: "Primary results", hint: "One row per candidate; rows with the same seat and area form one race.", fields: RESULT_FIELDS, query: useSiteResults, save: useSaveResult, del: useDeleteResult, name: (r) => `${r.candidate}, ${SEAT_LABEL[r.seat]} ${r.area}`, meta: (r) => `${formatNumber(r.votes)} votes · ${r.declared_on ? `declared ${formatDate(r.declared_on)}` : "counting"}${r.demo ? " · demo" : ""}` },
  ],
};

function CandidatesEditor() {
  const list = useSiteCandidates();
  const saveProfile = useSaveProfile();
  const [editing, setEditing] = useState(null);
  const rows = list.data || [];
  return (
    <div className="flex flex-wrap items-start gap-6">
      <Card variant="outline" className="min-w-0 flex-[1_1_420px] gap-3">
        <div className="flex flex-col gap-1">
          <CardTitle>Candidate profiles</CardTitle>
          <p className="text-small text-muted-foreground">Every approved aspirant. Write the profile from what the candidate sends, then publish it.</p>
        </div>
        {list.isLoading ? <LoadingText /> : null}
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
                <Button variant="quiet" onClick={() => setEditing(c)}>Edit profile</Button>
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
