// Pieces shared by the news, article and events pages.
import { Badge } from "@/components/ui/badge";
import { initials } from "@/lib/format";

export const LABELS = { statement: "Statement", news: "News", opinion: "Opinion" };

/** "3 November 2026" from an ISO date; pass `opts` for other parts. */
export const day = (iso, opts = { day: "numeric", month: "long", year: "numeric" }) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", opts) : "";

export function Photo({ url, className = "" }) {
  return url ? <img src={url} alt="" className={`object-cover ${className}`} /> : <div className={`ph ${className}`} />;
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
