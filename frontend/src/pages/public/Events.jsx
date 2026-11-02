// The party's own coming events, soonest first.
import { usePublicPosts } from "../../api/hooks";
import { ErrorState, LoadingState } from "../../components/ui";
import PostCard from "./PostCard";

export default function Events() {
  const events = usePublicPosts("event");
  return (
    <section className="site-section">
      <h1 className="site-title">Events</h1>
      {events.isLoading && <LoadingState />}
      {events.error && <ErrorState error={events.error} />}
      <div className="site-cards">
        {(events.data || []).map((post) => <PostCard key={post.id} post={post} />)}
      </div>
      {events.isSuccess && !events.data.length && (
        <p className="site-text">No events are planned right now.</p>
      )}
    </section>
  );
}
