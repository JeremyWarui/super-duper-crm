// /news: the lead story with three beside it, more stories, opinion, the latest rail and official statements.
import { useState } from "react";
import { Link } from "react-router-dom";
import { usePublicPosts } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { RailHead } from "@/components/ui/typography";
import { Initials, LABELS, Photo, StoryKicker, day } from "./story";

const PAGE = 20;
const short = (iso) => day(iso, { day: "numeric", month: "short" });

function Lead({ lead, beside }) {
  return (
    <section aria-label="Top stories" className="flex flex-wrap gap-8">
      <article className="flex min-w-0 flex-[3_1_560px] flex-col gap-3.5">
        <Link to={`/news/${lead.id}`} aria-hidden tabIndex={-1}><Photo url={lead.image_url} className="aspect-video w-full rounded-card" /></Link>
        <StoryKicker post={lead} />
        <h2 className="font-display text-[clamp(30px,3.6vw,44px)] leading-[1.08] font-extrabold tracking-[-0.02em]">
          <Link to={`/news/${lead.id}`} className="text-ink no-underline hover:text-primary">{lead.title}</Link>
        </h2>
        {lead.body ? <p className="line-clamp-2 max-w-[60ch] text-[18px] leading-[1.6] text-text-2">{lead.body}</p> : null}
        <span className="text-small text-muted-foreground">
          {lead.author ? `By ${lead.author} · ` : ""}{day(lead.published_on)} · {lead.read_minutes} min read
        </span>
      </article>
      <div className="flex min-w-0 flex-[2_1_320px] flex-col">
        {beside.map((n) => (
          <Link key={n.id} to={`/news/${n.id}`} className="flex gap-4 border-b border-line-2 py-4 text-ink no-underline first:pt-0 hover:text-primary">
            <Photo url={n.image_url} className="size-[104px] flex-none rounded-photo" />
            <span className="flex min-w-0 flex-col gap-1.5">
              <span className="text-meta font-extrabold uppercase tracking-[0.08em] text-primary">{LABELS[n.label] || "News"}</span>
              <span className="line-clamp-3 text-[18px] leading-[1.3] font-bold">{n.title}</span>
              <span className="text-small text-muted-foreground">{short(n.published_on)}</span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function More({ stories, offset, setOffset, full }) {
  return (
    <section aria-labelledby="more-h" className="flex flex-col gap-5">
      <div className="rule-top flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="more-h" className="font-display text-[26px] font-extrabold">More stories</h2>
        <span className="text-small text-muted-foreground">{stories.length} stories</span>
      </div>
      {stories.length ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-x-6 gap-y-8">
          {stories.map((n) => (
            <Link key={n.id} to={`/news/${n.id}`} className="flex flex-col gap-2 text-ink no-underline hover:text-primary">
              <Photo url={n.image_url} className="aspect-[16/10] w-full rounded-photo" />
              <span className="text-meta font-extrabold uppercase tracking-[0.08em] text-primary">{LABELS[n.label] || "News"}{n.place ? ` · ${n.place}` : ""}</span>
              <span className="text-[18px] leading-[1.3] font-bold">{n.title}</span>
              <span className="text-small text-muted-foreground">{day(n.published_on)} · {n.read_minutes} min read</span>
            </Link>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground">No more stories yet.</p>
      )}
      {offset > 0 || full ? (
        <div className="flex gap-2.5">
          {offset > 0 ? <Button variant="outline" onClick={() => setOffset(offset - PAGE)}>Newer</Button> : null}
          {full ? <Button variant="outline" onClick={() => setOffset(offset + PAGE)}>Older</Button> : null}
        </div>
      ) : null}
    </section>
  );
}

function Opinion() {
  const pieces = (usePublicPosts("news", 0, { label: "opinion" }).data || []).slice(0, 3);
  if (!pieces.length) return null;
  return (
    <section aria-labelledby="op-h" className="flex flex-col gap-5">
      <h2 id="op-h" className="rule-top font-display text-[26px] font-extrabold">Opinion</h2>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
        {pieces.map((o) => (
          <Card key={o.id} asChild interactive className="p-5">
            <Link to={`/news/${o.id}`}>
              <span className="flex items-center gap-3">
                <Initials name={o.author || "Writer"} url={o.author_photo_url} className="size-12 flex-none border-[3px] border-accent" />
                <span className="font-bold">{o.author || "Guest writer"}</span>
              </span>
              <span className="font-display text-[20px] leading-[1.25] font-extrabold">{o.title}</span>
            </Link>
          </Card>
        ))}
      </div>
      <p className="text-small text-muted-foreground">Opinion pieces are the writer's view. Official positions are published as statements.</p>
    </section>
  );
}

function Latest({ news }) {
  if (!news.length) return null;
  return (
    <section aria-labelledby="latest-h">
      <RailHead id="latest-h" accent>Latest</RailHead>
      <ol>
        {news.slice(0, 5).map((l) => (
          <li key={l.id} className="flex gap-3 border-b border-line-soft py-3">
            <span className="w-12 flex-none text-meta font-bold text-primary">{short(l.published_on)}</span>
            <Link to={`/news/${l.id}`} className="font-semibold leading-[1.4] text-ink no-underline hover:text-primary">{l.title}</Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Statements() {
  const list = (usePublicPosts("news", 0, { label: "statement" }).data || []).slice(0, 4);
  if (!list.length) return null;
  return (
    <Card asChild className="p-5">
      <section aria-labelledby="st-h">
        <RailHead id="st-h">Official statements</RailHead>
        {list.map((d) => (
          <Link key={d.id} to={`/news/${d.id}`} className="flex items-start justify-between gap-3 border-t border-line-soft pt-3 text-ink no-underline hover:text-primary">
            <span className="flex min-w-0 flex-col gap-1">
              <span className="font-bold leading-[1.35]">{d.title}</span>
              <span className="text-meta text-muted-foreground">
                {d.reference ? `Ref. ${d.reference} · ` : ""}{day(d.published_on)}{d.author ? ` · signed by ${d.author}` : ""}
              </span>
            </span>
            {d.pdf_url ? <span className="text-meta font-extrabold text-primary">PDF</span> : null}
          </Link>
        ))}
      </section>
    </Card>
  );
}

export default function News() {
  const [offset, setOffset] = useState(0);
  const news = usePublicPosts("news", offset);
  const posts = news.data || [];
  const top = offset === 0 ? posts.slice(0, 4) : [];
  const rest = offset === 0 ? posts.slice(4) : posts;
  return (
    <div className="site-container flex flex-col gap-12 pt-10 pb-[72px]">
      <h1 className="sr-only">News</h1>
      {news.isLoading ? <p className="text-muted-foreground">Loading…</p> : null}
      {news.error ? <p role="alert">{news.error.message}</p> : null}
      {news.isSuccess && !posts.length && offset === 0 ? <p className="text-muted-foreground">No news yet.</p> : null}
      {top.length ? <Lead lead={top[0]} beside={top.slice(1)} /> : null}
      {posts.length || offset > 0 ? (
        <div className="flex flex-wrap items-start gap-10">
          <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-12">
            <More stories={rest} offset={offset} setOffset={setOffset} full={posts.length === PAGE} />
            <Opinion />
          </div>
          <aside className="flex min-w-0 flex-[1_1_300px] flex-col gap-6">
            <Latest news={offset === 0 ? posts : []} />
            <Statements />
          </aside>
        </div>
      ) : null}
    </div>
  );
}
