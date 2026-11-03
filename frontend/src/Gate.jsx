import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useAuth } from "./store/auth";
import { useCampaigns, useMe } from "./api/hooks";
import { homeOf } from "./lib/home";
import Login from "./components/Login";
import Admin from "./components/Admin";
import NoCampaign from "./components/NoCampaign";
import CampaignClosed from "./components/CampaignClosed";
import CampaignLocked from "./components/CampaignLocked";
import App from "./App";
import Portal from "./pages/party/Portal";
import Join from "./components/Join";
import Withdraw from "./components/Withdraw";
import { PublicLayout } from "@/components/layout/PublicLayout";
import Legacy, { LegacySite } from "./components/Legacy";
import About from "./pages/public/About";
import Events from "./pages/public/Events";
import Home from "./pages/public/Home";
import Leadership from "./pages/public/Leadership";
import Manifesto from "./pages/public/Manifesto";
import News from "./pages/public/News";
import Post from "./pages/public/Post";
import JoinParty from "./pages/public/JoinParty";
import Contribute from "./pages/public/Contribute";
import Privacy from "./pages/public/Privacy";
import Unsubscribe from "./pages/public/Unsubscribe";
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
  if (campaigns.error?.code === "campaign_suspended") {
    return <Legacy><CampaignClosed message={campaigns.error.message} /></Legacy>;
  }
  if (campaigns.error?.code === "campaign_locked") {
    return <Legacy><CampaignLocked message={campaigns.error.message} /></Legacy>;
  }
  if (campaigns.isSuccess && campaigns.data.length === 0) {
    return partyRoles?.length ? <Portal /> : <Legacy><NoCampaign /></Legacy>;
  }
  return <App />;
}

// A superuser runs the deployment rather than a campaign, so they get the
// console at /console instead of the campaign gate, and the party portal under /party.
function Inside() {
  useMe();
  const isSuperuser = useAuth((s) => s.user?.is_superuser);
  const { pathname } = useLocation();
  if (isSuperuser) {
    if (pathname.startsWith("/party")) return <Portal />;
    if (pathname.startsWith("/console")) return <Admin />;
    return <Navigate to="/console" replace />;
  }
  return <SignedIn />;
}

export default function Root() {
  const token = useAuth((s) => s.token);
  const { pathname } = useLocation();
  if (!token) return pathname === "/signin" ? <Legacy><Login /></Legacy> : <Navigate to="/signin" replace />;
  // A new key per sign-in starts every screen fresh for the new user.
  return <Inside key={token} />;
}

function SignInPage() {
  const token = useAuth((s) => s.token);
  const user = useAuth((s) => s.user);
  return token ? <Navigate to={homeOf(user)} replace /> : <Login />;
}

function PostPage() {
  const { id } = useParams();
  return <Post key={id} id={id} />;
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

// The party's public site is at / and needs no login, nor do a sign-up link (/join/<code>),
// a supporter's withdrawal link (/withdraw/<code>) and the party's application and withdrawal
// pages. Every other address is a signed-in app.
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<PublicLayout><LegacySite><Home /></LegacySite></PublicLayout>} />
      <Route path="/about" element={<PublicLayout><LegacySite><About /></LegacySite></PublicLayout>} />
      <Route path="/leadership" element={<PublicLayout><LegacySite><Leadership /></LegacySite></PublicLayout>} />
      <Route path="/manifesto" element={<PublicLayout><LegacySite><Manifesto /></LegacySite></PublicLayout>} />
      <Route path="/news" element={<PublicLayout><LegacySite><News /></LegacySite></PublicLayout>} />
      <Route path="/news/:id" element={<PublicLayout><LegacySite><PostPage /></LegacySite></PublicLayout>} />
      <Route path="/events" element={<PublicLayout><LegacySite><Events /></LegacySite></PublicLayout>} />
      <Route path="/signin" element={<Legacy><SignInPage /></Legacy>} />
      <Route path="/join/:code" element={<Legacy><JoinPage /></Legacy>} />
      <Route path="/withdraw/:code" element={<Legacy><WithdrawPage /></Legacy>} />
      <Route path="/join-party" element={<PublicLayout><LegacySite><JoinParty /></LegacySite></PublicLayout>} />
      <Route path="/contribute" element={<PublicLayout><Contribute /></PublicLayout>} />
      <Route path="/privacy" element={<PublicLayout><Privacy /></PublicLayout>} />
      <Route path="/unsubscribe/:code" element={<PublicLayout><Unsubscribe /></PublicLayout>} />
      <Route path="/party/withdraw/:code" element={<Legacy><WithdrawPartyPage /></Legacy>} />
      <Route path="/party/volunteer/withdraw/:code" element={<Legacy><WithdrawVolunteerPage /></Legacy>} />
      <Route path="/*" element={<Root />} />
    </Routes>
  );
}
