import { useAuth } from "../store/auth";

// The party has suspended this campaign's aspirant, or the aspirant has withdrawn.
export default function CampaignClosed({ message }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  return (
    <div className="gate-no-campaign">
      <div className="gate-no-campaign-card">
        <div className="gate-no-campaign-title">{message}</div>
        <div className="gate-no-campaign-message">
          You are signed in as {user?.username}. Your campaign's data is kept, and the
          campaign opens again if the party reinstates its aspirant.
        </div>
        <button onClick={logout} className="gate-no-campaign-button">
          Sign out
        </button>
      </div>
    </div>
  );
}
