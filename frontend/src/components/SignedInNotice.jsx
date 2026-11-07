import { useAuth } from "../store/auth";

/** A full-page notice for a login with nowhere to go: "You are signed in as …" followed by `rest`, and Sign out. */
export default function SignedInNotice({ title, rest }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  return (
    <div className="gate-no-campaign">
      <div className="gate-no-campaign-card">
        <div className="gate-no-campaign-title">{title}</div>
        <div className="gate-no-campaign-message">You are signed in as {user?.username}{rest}</div>
        <button onClick={logout} className="gate-no-campaign-button">
          Sign out
        </button>
      </div>
    </div>
  );
}

/** For a login that is on no campaign: only the superuser puts logins on campaigns. */
export const NoCampaign = () => (
  <SignedInNotice
    title="You are not on a campaign yet"
    rest=", but this login is not on any campaign. Ask whoever runs your campaign, or contact support."
  />
);
