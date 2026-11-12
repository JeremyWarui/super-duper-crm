// Pieces shared by the home, news, article and events pages.
import { Link } from "react-router-dom";
import { Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { StoryMeta } from "@/components/ui/typography";
import { formatDay, initials } from "@/lib/format";

export const LABELS = { statement: "Statement", news: "News", opinion: "Opinion" };

export function Photo({ url, className = "" }) {
  return url ? <img src={url} alt="" className={`object-cover ${className}`} /> : <div className={`ph ${className}`} />;
}

/** The grid of square photo cards: tight gaps, as many columns as fit. */
export const PHOTO_GRID = "grid grid-cols-[repeat(auto-fill,minmax(min(260px,100%),1fr))] gap-3";

/**
 * A square card with the title over a dark fade on its photo; on hover or focus the party colour covers it.
 * With `to` it is a link; `foot` sits under the title.
 */
export function PhotoCard({ to, image, title, kicker, foot }) {
  const look = "group relative isolate flex aspect-square flex-col justify-end overflow-hidden rounded-photo bg-gradient-to-br from-ink-2 to-ink p-7 text-white no-underline";
  const inner = (
    <>
      {image ? <img src={image} alt="" className="absolute inset-0 -z-10 size-full object-cover transition-transform duration-500 group-hover:scale-105" /> : null}
      <span aria-hidden className="absolute inset-0 -z-10 bg-gradient-to-t from-ink via-ink/45 to-transparent" />
      <span aria-hidden className="absolute inset-0 -z-10 bg-primary opacity-0 transition-opacity duration-300 group-hover:opacity-95 group-focus-visible:opacity-95" />
      {kicker ? <span className="mb-2 font-display text-[18px] font-extrabold text-accent">{kicker}</span> : null}
      <span className="font-display text-[26px] leading-[1.15] font-extrabold tracking-[-0.01em] uppercase">{title}</span>
      {foot}
    </>
  );
  return to
    ? <Link to={to} className={`${look} hover:text-white focus-visible:outline-offset-4`}>{inner}</Link>
    : <div className={look}>{inner}</div>;
}

export function Initials({ name, url, className = "" }) {
  if (url) return <img src={url} alt="" className={`rounded-full object-cover ${className}`} />;
  const letters = initials(name);
  return <span aria-hidden className={`flex items-center justify-center rounded-full bg-primary-tint font-extrabold text-primary ${className}`}>{letters}</span>;
}

/** The label box and place over a story's headline: STATEMENT · NATIONAL. */
export function StoryKicker({ post }) {
  return (
    <span className="flex flex-wrap items-center gap-2.5">
      <Badge kind="label" tone={post.label === "statement" ? "primary" : "tint"}>{LABELS[post.label] || "News"}</Badge>
      {post.place ? <span className="text-meta font-extrabold uppercase tracking-[0.1em] text-muted-foreground">{post.place}</span> : null}
    </span>
  );
}

/** A story as a card: photo, label and place, headline, then date and reading time. */
export function StoryCard({ post }) {
  return (
    <Link to={`/news/${post.id}`} className="flex flex-col gap-2 text-ink no-underline hover:text-primary">
      <Photo url={post.image_url} className="aspect-[16/10] w-full rounded-photo" />
      <StoryMeta category={LABELS[post.label] || "News"} place={post.place} />
      <span className="text-[18px] leading-[1.3] font-bold">{post.title}</span>
      <span className="text-small text-muted-foreground">{formatDay(post.published_on)} · {post.read_minutes} min read</span>
    </Link>
  );
}

/** A story as a row beside the lead: a small photo, label, headline and `when`. */
export function StoryRow({ post, when, photoClass = "size-[104px]" }) {
  return (
    <Link to={`/news/${post.id}`} className="flex gap-4 border-b border-line-2 py-4 text-ink no-underline first:pt-0 hover:text-primary">
      <Photo url={post.image_url} className={`${photoClass} flex-none rounded-photo`} />
      <span className="flex min-w-0 flex-col gap-1.5">
        <StoryMeta category={LABELS[post.label] || "News"} place={post.place} />
        <span className="line-clamp-3 text-[18px] leading-[1.3] font-bold">{post.title}</span>
        <span className="text-small text-muted-foreground">{when}</span>
      </span>
    </Link>
  );
}

/** YouTube's own thumbnail for a YouTube link, else nothing. */
export function youtubeThumb(url) {
  const id = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/))([\w-]{11})/)?.[1];
  return id ? `https://img.youtube.com/vi/${id}/hqdefault.jpg` : "";
}

/** A video as a card: its thumbnail with a play button and running time, then its title. */
export function VideoCard({ video }) {
  const thumb = video.thumbnail_url || youtubeThumb(video.url);
  return (
    <a href={video.url} target="_blank" rel="noreferrer" className="group flex flex-col gap-2 text-ink no-underline hover:text-primary">
      <span className="relative flex aspect-video items-center justify-center overflow-hidden rounded-photo bg-[#34443B]">
        {thumb ? <img src={thumb} alt="" className="absolute inset-0 size-full object-cover" /> : null}
        <span aria-hidden className="relative flex size-[46px] items-center justify-center rounded-full bg-accent text-ink transition-transform group-hover:scale-110"><Play className="size-[18px] translate-x-px fill-current" /></span>
        {video.duration ? <span className="absolute right-2.5 bottom-2.5 rounded-sm bg-black/60 px-2 py-[3px] text-meta font-bold text-white">{video.duration}</span> : null}
      </span>
      <span className="leading-[1.35] font-bold">{video.title}</span>
    </a>
  );
}

/** A list of [label, path] links with arrows, as on the hero card beside the carousel. */
export function QuickLinks({ links }) {
  return (
    <div className="flex flex-col border-t border-line-2">
      {links.map(([label, to]) => (
        <Link key={to} to={to} className="flex justify-between border-b border-line-soft py-3 font-semibold text-ink no-underline last:border-0 hover:text-primary">
          <span>{label}</span><span aria-hidden>→</span>
        </Link>
      ))}
    </div>
  );
}
