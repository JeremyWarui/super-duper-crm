import { Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "./store/auth";
import { useCampaigns, useMe } from "./api/hooks";
import Login from "./components/Login";
import Admin from "./components/Admin";
import NoCampaign from "./components/NoCampaign";
import App from "./App";
import Portal from "./pages/party/Portal";
import Join from "./components/Join";
import Withdraw from "./components/Withdraw";
import JoinParty from "./pages/public/JoinParty";
import WithdrawParty from "./pages/public/WithdrawParty";
import WithdrawVolunteer from "./pages/public/WithdrawVolunteer";

/** Drop every cached read when the signed-in user changes, so nobody sees the last user's data. */
export function forgetOnSwitch(queryClient) {
  return useAuth.subscribe((state, prev) => {
    if (state.token !== prev.token) queryClient.clear();
  });
}

// A login on a campaign gets the campaign app; one on none but holding a party
// role gets the party portal; anyone else waits to be put on a campaign.
function SignedIn() {
  const campaigns = useCampaigns();
  const partyRoles = useAuth((s) => s.user?.party_roles);
  const staff = useAuth((s) => s.user?.role === null);
  // A staff login is never on a campaign, so it needs no campaign list to be routed.
  if (staff && partyRoles?.length) return <Portal />;
  if (campaigns.isSuccess && campaigns.data.length === 0) {
    return partyRoles?.length ? <Portal /> : <NoCampaign />;
  }
  return <App />;
}

// A superuser runs the deployment rather than a campaign, so they get the
// console instead of the campaign gate.
function Inside() {
  useMe();
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

function WithdrawPartyPage() {
  return <WithdrawParty code={useParams().code} />;
}

function WithdrawVolunteerPage() {
  return <WithdrawVolunteer code={useParams().code} />;
}

// A sign-up link opens /join/<code>, and a supporter's withdrawal link /withdraw/<code>;
// neither needs a login. The party's application form and withdrawal page are public too.
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/join/:code" element={<JoinPage />} />
      <Route path="/withdraw/:code" element={<WithdrawPage />} />
      <Route path="/join-party" element={<JoinParty />} />
      <Route path="/party/withdraw/:code" element={<WithdrawPartyPage />} />
      <Route path="/party/volunteer/withdraw/:code" element={<WithdrawVolunteerPage />} />
      <Route path="/*" element={<Root />} />
    </Routes>
  );
}
