// /candidates: the party's listed aspirants, by seat, county and a name or area search.
import { useState } from "react";
import { Link } from "react-router-dom";
import { usePartyPlaces, usePublicCandidates } from "@/api/hooks";
import { Card } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Crumbs } from "@/components/ui/typography";
import { SEATS } from "@/pages/party/helpers";
import { Photo } from "./story";

export const SEAT_NAME = Object.fromEntries(SEATS.map(([value, label]) => [value, label]));

export function CandidateCard({ c, square = false }) {
  return (
    <Card asChild interactive className="gap-0 overflow-hidden p-0">
      <Link to={`/candidates/${c.slug}`}>
        <Photo url={c.photo_url} className={`${square ? "aspect-square" : "aspect-[4/3]"} w-full`} />
        <span className="flex flex-1 flex-col gap-1.5 p-[18px]">
          <span className="text-meta font-extrabold uppercase tracking-[0.08em] text-primary">{SEAT_NAME[c.seat]}</span>
          <span className="text-[18px] font-bold">{c.name}</span>
          <span className="text-small text-muted-foreground">{[c.area, c.county].filter((v, i, all) => v && all.indexOf(v) === i).join(" · ")}</span>
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
  const pill = (on) => `min-h-11 cursor-pointer rounded-full border-[1.5px] px-[18px] text-[15px] font-semibold ${on ? "border-ink bg-ink text-white" : "border-line-control bg-white text-ink"}`;
  return (
    <>
      <section className="bg-primary text-white">
        <div className="site-container flex flex-col gap-[22px] py-12">
          <Crumbs onDark items={[{ label: "Home", to: "/" }, { label: "Candidates" }]} />
          <h1 className="font-display text-[clamp(40px,5vw,64px)] leading-none font-extrabold tracking-[-0.03em]">Our candidates</h1>
          <p className="max-w-[60ch] text-[18px] text-[#CFE0D5]">Find the party's aspirant for your ward, constituency and county.</p>
          <div className="flex flex-wrap items-end gap-3.5">
            <label className="flex flex-[1_1_280px] flex-col gap-1.5 text-small font-semibold text-[#DDE3DF]">
              Search by name or area
              <Input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="A name, ward or constituency" className="border-0 text-ink" />
            </label>
            <label className="flex min-w-[200px] flex-col gap-1.5 text-small font-semibold text-[#DDE3DF]">
              County
              <NativeSelect value={county} onChange={(e) => setCounty(e.target.value)} className="border-0 bg-white text-ink">
                <option value="">All counties</option>
                {counties.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </NativeSelect>
            </label>
          </div>
        </div>
      </section>
      <div className="site-container flex flex-col gap-6 pt-9 pb-20">
        <div role="group" aria-label="Filter by seat" className="flex flex-wrap gap-2">
          <button type="button" aria-pressed={!seat} onClick={() => setSeat("")} className={pill(!seat)}>All</button>
          {SEATS.map(([value, label]) => (
            <button key={value} type="button" aria-pressed={seat === value} onClick={() => setSeat(value)} className={pill(seat === value)}>{label}</button>
          ))}
        </div>
        {list.isSuccess ? <p className="text-[15px] text-muted-foreground"><strong className="text-ink">{people.length}</strong> {people.length === 1 ? "aspirant" : "aspirants"} shown</p> : null}
        {list.isLoading ? <p className="text-muted-foreground">Loading…</p> : null}
        {list.error ? <p role="alert">{list.error.message}</p> : null}
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
