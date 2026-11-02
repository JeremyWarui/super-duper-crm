// One published news item or event, in full.
import { Link } from "react-router-dom";
import { usePublicPost } from "../../api/hooks";
import { ErrorState, LoadingState } from "../../components/ui";
import { formatDate } from "../../lib/format";

export default function Post({ id }) {
  const post = usePublicPost(id);
  if (post.isLoading) return <LoadingState />;
  if (post.error) return <ErrorState error={post.error} />;
  const p = post.data;
  const event = p.kind === "event";
  return (
    <article className="site-section">
      <Link className="site-link" to={event ? "/events" : "/news"}>
        {event ? "All events" : "All news"}
      </Link>
      <h1 className="site-title">{p.title}</h1>
      <div className="site-card-date">
        {formatDate(event ? p.event_date : p.published_on)}
        {event && p.venue ? ` · ${p.venue}` : ""}
      </div>
      {p.image_url && <img className="site-image" src={p.image_url} alt="" />}
      <p className="site-text">{p.body}</p>
    </article>
  );
}
