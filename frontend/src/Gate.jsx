import { useAuth } from "./store/auth";
import { useCampaigns } from "./api/hooks";
import Login from "./components/Login";
import Admin from "./components/Admin";
import App from "./App";

/** Drop every cached read when the signed-in user changes, so nobody sees the last user's data. */
export function forgetOnSwitch(queryClient) {
  return useAuth.subscribe((state, prev) => {
    if (state.token !== prev.token) queryClient.clear();
  });
}

// Only the superuser creates campaigns, so a login on none waits to be put on one.
function NoCampaign() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#E9EBE6",
        color: "#171C1F",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 420,
          background: "#FFFFFF",
          border: "1px solid #D7DBD4",
          borderRadius: 14,
          padding: 24,
        }}
      >
        <div
          style={{
            fontFamily: "Oswald, Impact, sans-serif",
            fontSize: 20,
            fontWeight: 600,
          }}
        >
          You are not on a campaign yet
        </div>
        <div
          style={{
            fontSize: 13.5,
            color: "#5C655F",
            marginTop: 8,
            lineHeight: 1.5,
          }}
        >
          You are signed in as {user?.username}, but this login is not on any
          campaign. Ask whoever runs your campaign, or contact support.
        </div>
        <button
          onClick={logout}
          style={{
            marginTop: 18,
            padding: "8px 14px",
            borderRadius: 8,
            border: "1px solid #D7DBD4",
            background: "#FFFFFF",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

function SignedIn() {
  const campaigns = useCampaigns();
  return campaigns.isSuccess && campaigns.data.length === 0 ? (
    <NoCampaign />
  ) : (
    <App />
  );
}

// A superuser runs the deployment rather than a campaign, so they get the
// console instead of the campaign gate.
function Inside() {
  const isSuperuser = useAuth((s) => s.user?.is_superuser);
  return isSuperuser ? <Admin /> : <SignedIn />;
}

export default function Root() {
  const token = useAuth((s) => s.token);
  // A new key per sign-in starts every screen fresh for the new user.
  return token ? <Inside key={token} /> : <Login />;
}
