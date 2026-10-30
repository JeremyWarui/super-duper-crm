import { Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "./store/auth";
import { useCampaigns } from "./api/hooks";
import Login from "./components/Login";
import Admin from "./components/Admin";
import App from "./App";
import Join from "./components/Join";
import Withdraw from "./components/Withdraw";

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
    <div className="gate-no-campaign">
      <div className="gate-no-campaign-card">
        <div className="gate-no-campaign-title">
          You are not on a campaign yet
        </div>
        <div className="gate-no-campaign-message">
          You are signed in as {user?.username}, but this login is not on any
          campaign. Ask whoever runs your campaign, or contact support.
        </div>
        <button onClick={logout} className="gate-no-campaign-button">
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

function JoinPage() {
  return <Join code={useParams().code} />;
}

function WithdrawPage() {
  return <Withdraw code={useParams().code} />;
}

// A sign-up link opens /join/<code>, and a supporter's withdrawal link /withdraw/<code>;
// neither needs a login.
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/join/:code" element={<JoinPage />} />
      <Route path="/withdraw/:code" element={<WithdrawPage />} />
      <Route path="/*" element={<Root />} />
    </Routes>
  );
}
