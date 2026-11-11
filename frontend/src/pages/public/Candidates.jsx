// /candidates: the party's listed aspirants, by seat, county and a name or area search.
import { useState } from "react";
import { Link } from "react-router-dom";
import { usePartyPlaces, usePublicCandidates } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { FilterSelect, Input } from "@/components/ui/input";
import { SEAT_LABEL, SEATS } from "@/lib/labels";
import { Photo } from "./story";
import { LoadingText } from "@/components/ui/loading-text";
import { ErrorText } from "@/components/ui/error-text";
import { PageHero } from "@/components/PageHead";
import { FilterPills } from "@/components/ui/tabs";
import { whereOf } from "@/lib/format";
import { StoryMeta } from "@/components/ui/typography";


export function CandidateCard({ c, square = false }) {
  return (
    <Card asChild interactive className="gap-0 overflow-hidden p-0">
      <Link to={`/candidates/${c.slug}`}>
        <Photo url={c.photo_url} className={`${square ? "aspect-square" : "aspect-[4/3]"} w-full`} />
        <span className="flex flex-1 flex-col gap-1.5 p-[18px]">
          <StoryMeta category={SEAT_LABEL[c.seat]} />
          <span className="text-[18px] font-bold">{c.name}</span>
          <span className="text-small text-muted-foreground">{whereOf(c, " · ")}</span>
          <span className="mt-auto pt-2 text-small font-bold text-primary">View profile →</span>
        </span>
      </Link>
    </Card>
  );
}

export default function Candidates() {
  const [seat, setSeat] = useState("");
  const [county, setCounty] = useState("");
  const [q, setQ] = useState("");
  const counties = usePartyPlaces().data || [];
  const list = usePublicCandidates({ seat, county, q: q.trim() });
  const people = list.data || [];
  return (
    <>
      <PageHero crumbs={[{ label: "Candidates" }]} title="Our candidates" lead="Find the party's aspirant for your ward, constituency and county.">
        <div className="flex flex-wrap items-end gap-3.5">
          <label className="flex flex-[1_1_280px] flex-col gap-1.5 text-small font-semibold text-[#DDE3DF]">
            Search by name or area
            <Input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="A name, ward or constituency" className="border-0 text-ink" />
          </label>
          <label className="flex min-w-[200px] flex-col gap-1.5 text-small font-semibold text-[#DDE3DF]">
            County
            <FilterSelect label="County" blank="All counties" value={county} onChange={setCounty} options={counties} className="w-full flex-none border-0 bg-white text-ink" />
          </label>
        </div>
      </PageHero>
      <div className="site-container flex flex-col gap-6 pt-9 pb-20">
        <FilterPills look="ink" label="Filter by seat" options={[["", "All"], ...SEATS.map(([value, label]) => [value, label])]} value={seat} onChange={setSeat} />
        {list.isSuccess ? <p className="text-[15px] text-muted-foreground"><strong className="text-ink">{people.length}</strong> {people.length === 1 ? "aspirant" : "aspirants"} shown</p> : null}
        {list.isLoading ? <LoadingText /> : null}
        {list.error ? <ErrorText error={list.error} /> : null}
        <div className="grid grid-cols-[repeat(auto-fill,minmax(min(230px,100%),1fr))] gap-5">
          {people.map((c) => <CandidateCard key={c.slug} c={c} />)}
        </div>
        {list.isSuccess && !people.length ? (
          <div className="rounded-card border border-dashed border-line-control bg-white p-8 text-center text-muted-foreground">
            No candidates match these filters yet. <Link to="/vie" className="font-bold">Thinking of vying?</Link>
          </div>
        ) : null}
        <p className="text-small text-muted-foreground">Aspirants are listed while nominations are open, once the party publishes their profile.</p>
      </div>
    </>
  );
}
