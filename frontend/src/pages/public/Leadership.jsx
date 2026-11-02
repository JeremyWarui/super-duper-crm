// The party's published leaders, in the order it set.
import { usePublicLeaders } from "../../api/hooks";
import { ErrorState, LoadingState } from "../../components/ui";

export default function Leadership() {
  const leaders = usePublicLeaders();
  return (
    <section className="site-section">
      <h1 className="site-title">Leadership</h1>
      {leaders.isLoading && <LoadingState />}
      {leaders.error && <ErrorState error={leaders.error} />}
      <div className="site-cards">
        {(leaders.data || []).map((leader) => (
          <article key={leader.id} className="site-card">
            {leader.photo_url && <img className="site-card-image" src={leader.photo_url} alt="" />}
            <div className="site-card-title">{leader.name}</div>
            <div className="site-card-date">{leader.position}</div>
            {leader.bio && <p className="site-card-text">{leader.bio}</p>}
          </article>
        ))}
      </div>
      {leaders.isSuccess && !leaders.data.length && (
        <p className="site-text">The party has not listed its leaders yet.</p>
      )}
    </section>
  );
}
