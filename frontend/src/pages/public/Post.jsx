// /news/:id: one published story or event in full; a statement carries its official record.
import { Link } from "react-router-dom";
import { usePublicPost, usePublicPosts } from "@/api/hooks";
import { PdfViewer } from "@/components/PdfViewer";
import { RichText } from "@/components/RichTextView";
import { Card } from "@/components/ui/card";
import { Crumbs, RailHead } from "@/components/ui/typography";
import { formatDay } from "@/lib/format";
import { Initials, LABELS, Photo, StoryKicker } from "./story";

function Record({ post }) {
  return (
    <section aria-labelledby="rec-h" className="flex flex-col gap-3 rounded-xl border border-line border-l-4 border-l-primary bg-white p-5">
      <h2 id="rec-h" className="text-ui font-extrabold uppercase tracking-[0.12em]">Official record</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[15px]">
        {post.reference ? <><dt className="text-muted-foreground">Reference</dt><dd className="font-semibold">{post.reference}</dd></> : null}
        {post.author ? <><dt className="text-muted-foreground">Issued by</dt><dd className="font-semibold">{post.author}</dd></> : null}
        <dt className="text-muted-foreground">Date issued</dt><dd className="font-semibold">{formatDay(post.published_on)}</dd>
      </dl>
    </section>
  );
}

function ReadNext({ id }) {
  const next = (usePublicPosts("news").data || []).filter((n) => n.id !== id).slice(0, 3);
  if (!next.length) return null;
  return (
    <section aria-labelledby="next-h" className="flex flex-col gap-5">
      <h2 id="next-h" className="rule-top font-display text-[26px] font-extrabold">Read next</h2>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-6">
        {next.map((n) => (
          <Link key={n.id} to={`/news/${n.id}`} className="flex flex-col gap-2 text-ink no-underline hover:text-primary">
            <Photo url={n.image_url} className="aspect-[16/10] w-full rounded-photo" />
            <span className="text-meta font-extrabold uppercase tracking-[0.08em] text-primary">{LABELS[n.label] || "News"}</span>
            <span className="text-[18px] leading-[1.3] font-bold">{n.title}</span>
            <span className="text-small text-muted-foreground">{formatDay(n.published_on)} · {n.read_minutes} min read</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function LatestStatements({ id }) {
  const list = (usePublicPosts("news", 0, { label: "statement" }).data || []).filter((s) => s.id !== id).slice(0, 4);
  if (!list.length) return null;
  return (
    <Card asChild className="p-5">
      <section aria-labelledby="rel-h">
        <RailHead id="rel-h">Latest statements</RailHead>
        {list.map((r) => (
          <Link key={r.id} to={`/news/${r.id}`} className="flex flex-col gap-1 border-t border-line-soft pt-2.5 text-ink no-underline hover:text-primary">
            <span className="text-meta font-bold text-primary">{formatDay(r.published_on)}</span>
            <span className="text-[15px] leading-[1.35] font-bold">{r.title}</span>
          </Link>
        ))}
      </section>
    </Card>
  );
}

export default function Post({ id }) {
  const post = usePublicPost(id);
  if (post.isLoading) return <div className="site-container py-12 text-muted-foreground">Loading…</div>;
  if (post.error) return <div role="alert" className="site-container py-12">{post.error.message}</div>;
  const p = post.data;
  const event = p.kind === "event";
  const section = event ? { label: "Events", to: "/events" } : { label: "News", to: "/news" };
  return (
    <div className="site-container flex flex-col gap-14 pt-10 pb-[72px]">
      <div className="flex flex-wrap items-start gap-12">
        <article className="flex min-w-0 max-w-[760px] flex-[999_1_560px] flex-col gap-[22px]">
          <Crumbs items={[{ label: "Home", to: "/" }, section, { label: event ? p.title : LABELS[p.label] || "News" }]} />
          {event ? null : <StoryKicker post={p} />}
          <h1 className="font-display text-[clamp(34px,4.5vw,52px)] leading-[1.05] font-extrabold tracking-[-0.02em]">{p.title}</h1>
          <div className="flex items-center gap-2.5 border-y border-line-2 py-3.5">
            {event ? (
              <span className="flex flex-col">
                <strong className="text-[15px]">{formatDay(p.event_date, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</strong>
                <span className="text-small text-muted-foreground">{[p.venue, p.county?.name].filter(Boolean).join(" · ")}</span>
              </span>
            ) : (
              <>
                {p.author ? <Initials name={p.author} url={p.author_photo_url} className="size-10 flex-none" /> : null}
                <span className="flex flex-col">
                  {p.author ? <strong className="text-[15px]">{p.author}</strong> : null}
                  <span className="text-small text-muted-foreground">Published {formatDay(p.published_on)} · {p.read_minutes} min read</span>
                </span>
              </>
            )}
          </div>
          {p.image_url ? <img src={p.image_url} alt="" className="aspect-video w-full rounded-photo object-cover" /> : null}
          {p.body ? <RichText html={p.body} className="text-[18px] leading-[1.75]" /> : null}
          {p.label === "statement" && !event ? <Record post={p} /> : null}
          {p.label === "statement" && !event && p.pdf_url ? <PdfViewer url={p.pdf_url} title="The signed statement" /> : null}
        </article>
        <aside className="flex min-w-0 flex-[1_1_300px] flex-col gap-[18px]">
          <LatestStatements id={p.id} />
        </aside>
      </div>
      <ReadNext id={p.id} />
    </div>
  );
}
