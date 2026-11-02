// The party's published news, newest first, 20 at a time.
import { useState } from "react";
import { usePublicPosts } from "../../api/hooks";
import { Button, ErrorState, LoadingState } from "../../components/ui";
import PostCard from "./PostCard";

const PAGE = 20;

export default function News() {
  const [offset, setOffset] = useState(0);
  const news = usePublicPosts("news", offset);
  const posts = news.data || [];
  return (
    <section className="site-section">
      <h1 className="site-title">News</h1>
      {news.isLoading && <LoadingState />}
      {news.error && <ErrorState error={news.error} />}
      <div className="site-cards">
        {posts.map((post) => <PostCard key={post.id} post={post} />)}
      </div>
      {news.isSuccess && !posts.length && <p className="site-text">No news yet.</p>}
      <div className="site-pager">
        {offset > 0 && <Button onClick={() => setOffset(offset - PAGE)}>Newer</Button>}
        {posts.length === PAGE && <Button onClick={() => setOffset(offset + PAGE)}>Older</Button>}
      </div>
    </section>
  );
}
