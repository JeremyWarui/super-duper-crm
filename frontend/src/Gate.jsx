import { useAuth } from "./store/auth";
import { useCampaigns } from "./api/hooks";
import Login from "./components/Login";
import Onboarding from "./components/Onboarding";
import Admin from "./components/Admin";
import App from "./App";

/** Drop every cached read when the signed-in user changes, so nobody sees the last user's data. */
export function forgetOnSwitch(queryClient) {
  return useAuth.subscribe((state, prev) => {
    if (state.token !== prev.token) queryClient.clear();
  });
}

// Signed in with no campaign -> set one up. A mobilizer cannot, so they skip it.
function SignedIn() {
  const role = useAuth((s) => s.user?.role);
  const campaigns = useCampaigns();
  const needsSetup =
    campaigns.isSuccess && campaigns.data.length === 0 && role !== "mobilizer";
  return needsSetup ? (
    <Onboarding onDone={() => campaigns.refetch()} />
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
