// The party's public home page: who it is, its latest news and next events.
import { Link } from "react-router-dom";
import { useParty, usePublicPosts } from "../../api/hooks";
import PostCard from "./PostCard";

function Latest({ title, kind, to }) {
  const posts = usePublicPosts(kind).data || [];
  if (!posts.length) return null;
  return (
    <section className="site-section">
      <h2 className="site-section-title">{title}</h2>
      <div className="site-cards">
        {posts.slice(0, 3).map((post) => <PostCard key={post.id} post={post} />)}
      </div>
      <Link className="site-link" to={to}>See all</Link>
    </section>
  );
}

export default function Home() {
  const party = useParty().data;
  return (
    <>
      <section className="site-hero">
        <h1 className="site-title">{party?.name || "Welcome"}</h1>
        {party?.description && <p className="site-lead">{party.description}</p>}
        <Link className="site-button" to="/join-party">Join the party</Link>
      </section>
      <Latest title="Latest news" kind="news" to="/news" />
      <Latest title="Coming events" kind="event" to="/events" />
    </>
  );
}
