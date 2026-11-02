// One news item or event in a list: its date, title, and the start of its text.
import { Link } from "react-router-dom";
import { formatDate } from "../../lib/format";

export default function PostCard({ post }) {
  const event = post.kind === "event";
  return (
    <article className="site-card">
      {post.image_url && <img className="site-card-image" src={post.image_url} alt="" />}
      <div className="site-card-date">
        {formatDate(event ? post.event_date : post.published_on)}
        {event && post.venue ? ` · ${post.venue}` : ""}
      </div>
      <Link className="site-card-title" to={`/news/${post.id}`}>
        {post.title}
      </Link>
      {post.body && <p className="site-card-text">{post.body.slice(0, 200)}</p>}
    </article>
  );
}
