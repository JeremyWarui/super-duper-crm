import { useRef } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useAuth } from "./store/auth";
import { useCampaigns, useMe } from "./api/hooks";
import { homeOf, landingOf } from "./lib/home";
import Login from "./components/Login";
import Admin from "./components/Admin";
import NoCampaign from "./components/NoCampaign";
import CampaignClosed from "./components/CampaignClosed";
import App from "./App";
import Portal from "./pages/party/Portal";
import Join from "./components/Join";
import Withdraw from "./components/Withdraw";
import { PublicLayout } from "@/components/layout/PublicLayout";
import Legacy from "./components/Legacy";
import About from "./pages/public/About";
import Events from "./pages/public/Events";
import Home from "./pages/public/Home";
import AspirantHome, { AspirantAbout, AspirantAgenda, AspirantMedia } from "./pages/public/AspirantHome";
import Volunteer from "./pages/public/Volunteer";
import { useInstall } from "./app/site";
import Setup from "./pages/setup/Setup";
import Leadership from "./pages/public/Leadership";
import Manifesto from "./pages/public/Manifesto";
import Results from "./pages/public/Results";
import Candidates from "./pages/public/Candidates";
import CandidatePage from "./pages/public/Candidate";
import CandidateWithdraw from "./pages/public/CandidateWithdraw";
import Vie from "./pages/public/Vie";
import News from "./pages/public/News";
import Post from "./pages/public/Post";
import JoinParty from "./pages/public/JoinParty";
import ForgotPassword from "./pages/public/ForgotPassword";
import SetPassword from "./pages/public/SetPassword";
import TeamSignup from "./pages/public/TeamSignup";
import Contribute from "./pages/public/Contribute";
import Privacy from "./pages/public/Privacy";
import Unsubscribe from "./pages/public/Unsubscribe";
import Chooser from "./pages/public/Chooser";
import Branch from "./pages/public/Branch";
import Issue from "./pages/public/Issue";
import Branches from "./pages/public/Branches";
import Account from "./pages/member/Account";
import WithdrawParty from "./pages/public/WithdrawParty";
import WithdrawVolunteer from "./pages/public/WithdrawVolunteer";

// The public site settings: the same for everyone, so they outlive a change of user.
const PUBLIC = (query) => query.queryKey.length === 1 && query.queryKey[0] === "site";

/** Drop every cached read but the public site settings when the signed-in user changes, so
nobody sees the last user's data.

A new token for the same user keeps them.
*/
export function forgetOnSwitch(queryClient) {
  return useAuth.subscribe((state, prev) => {
    const sameUser = state.token && prev.token && state.user?.id === prev.user?.id;
    if (state.token !== prev.token && !sameUser) queryClient.removeQueries({ predicate: (q) => !PUBLIC(q) });
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
  if (campaigns.isSuccess && campaigns.data.length === 0) {
    return partyRoles?.length ? <Portal /> : <Legacy><NoCampaign /></Legacy>;
  }
  return <App />;
}

// A superuser runs the deployment rather than a campaign, so they get the
// console at /console instead of the campaign gate, and in a party installation the party
// portal under /party. Both wait until the installation's type is known.
function Inside() {
  useMe();
  const install = useInstall();
  const isSuperuser = useAuth((s) => s.user?.is_superuser);
  const isMember = useAuth((s) => s.user?.kind === "member");
  const { pathname } = useLocation();
  // A member login opens only its own account.
  if (isMember) return <Navigate to="/account" replace />;
  if (isSuperuser) {
    if (install.loading) return null;
    if (pathname.startsWith("/party")) return install.aspirant ? <Navigate to="/console" replace /> : <Portal />;
    if (pathname.startsWith("/console")) return <Admin />;
    return <Navigate to="/console" replace />;
  }
  return <SignedIn />;
}

export default function Root() {
  const token = useAuth((s) => s.token);
  const { pathname } = useLocation();
  if (!token) return pathname === "/signin" ? <Login /> : <Navigate to="/signin" replace />;
  // A new key per sign-in starts every screen fresh for the new user.
  return <Inside key={token} />;
}

function SignInPage() {
  const token = useAuth((s) => s.token);
  const user = useAuth((s) => s.user);
  return token ? <Navigate to={landingOf(user)} replace /> : <Login />;
}

/** Pages for a signed-in login only; without one, sign-in. */
function SignedInOnly({ children }) {
  const token = useAuth((s) => s.token);
  return token ? children : <Navigate to="/signin" replace />;
}

/** The chooser offers a member's account beside the work, which only a party installation has. */
function ChooserPage() {
  const install = useInstall();
  const user = useAuth((s) => s.user);
  if (install.loading) return null;
  return install.aspirant ? <Navigate to={homeOf(user)} replace /> : <Chooser />;
}

function AccountPage() {
  useMe();
  const user = useAuth((s) => s.user);
  if (!user?.member_account) return <Navigate to={landingOf(user)} replace />;
  return <PublicLayout><Account /></PublicLayout>;
}

function CandidateRoute() {
  const { slug } = useParams();
  return <CandidatePage key={slug} slug={slug} />;
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

const page = (element) => <PublicLayout>{element}</PublicLayout>;

// The website pages both kinds of installation serve, and those of each kind. A path only the
// other kind serves goes home.
const SHARED = [
  ["/news", () => page(<News />)],
  ["/news/:id", () => page(<PostPage />)],
  ["/events", () => page(<Events />)],
  ["/contribute", () => page(<Contribute />)],
  ["/privacy", () => page(<Privacy />)],
  ["/unsubscribe/:code", () => page(<Unsubscribe />)],
  ["/issues/:id", () => page(<Issue />)],
  ["/signin", () => <SignInPage />],
  ["/signin/where", () => <SignedInOnly><ChooserPage /></SignedInOnly>],
  ["/forgot-password", () => page(<ForgotPassword />)],
  ["/invite/:token", () => page(<SetPassword />)],
  ["/reset/:token", () => page(<SetPassword />)],
  ["/team/:code", () => page(<TeamSignup />)],
  ["/account", () => <SignedInOnly><AccountPage /></SignedInOnly>],
  ["/join/:code", () => <Legacy><JoinPage /></Legacy>],
  ["/withdraw/:code", () => <Legacy><WithdrawPage /></Legacy>],
];

const PARTY = [
  ["/", () => page(<Home />)],
  ["/about", () => page(<About />)],
  ["/leadership", () => page(<Leadership />)],
  ["/manifesto", () => page(<Manifesto />)],
  ["/results", () => page(<Results />)],
  ["/candidates", () => page(<Candidates />)],
  ["/candidates/volunteer/withdraw/:code", () => page(<CandidateWithdraw />)],
  ["/candidates/:slug", () => page(<CandidateRoute />)],
  ["/vie", () => page(<Vie />)],
  ["/join-party", () => page(<JoinParty />)],
  ["/counties", () => page(<Branches />)],
  ["/counties/:id", () => page(<Branch />)],
  ["/party/withdraw/:code", () => <Legacy><WithdrawPartyPage /></Legacy>],
  ["/party/volunteer/withdraw/:code", () => <Legacy><WithdrawVolunteerPage /></Legacy>],
];

const ASPIRANT = [
  ["/", () => page(<AspirantHome />)],
  ["/about", () => page(<AspirantAbout />)],
  ["/agenda", () => page(<AspirantAgenda />)],
  ["/media", () => page(<AspirantMedia />)],
  ["/volunteer", () => page(<Volunteer />)],
  ["/volunteer/withdraw/:code", () => page(<CandidateWithdraw />)],
];

const home = <Navigate to="/" replace />;

// Everything else is a signed-in app.
export function AppRoutes() {
  const install = useInstall();
  // Latched: a refetch or finishing setup must not swap the wizard out mid-way.
  const settingUp = useRef(false);
  if (install.notSetUp) settingUp.current = true;
  if (settingUp.current) {
    return (
      <Routes>
        <Route path="/setup" element={<Setup />} />
        <Route path="*" element={<Navigate to="/setup" replace />} />
      </Routes>
    );
  }
  const own = install.aspirant ? ASPIRANT : PARTY;
  const other = install.aspirant ? PARTY : ASPIRANT;
  const taken = new Set(own.map(([path]) => path));
  // Until the site settings say which kind this is, its own pages wait rather than guess.
  const typed = install.loading
    ? [...PARTY, ...ASPIRANT].map(([path]) => <Route key={path} path={path} element={null} />)
    : [
        ...own.map(([path, element]) => <Route key={path} path={path} element={element()} />),
        ...other.filter(([path]) => !taken.has(path)).map(([path]) => <Route key={path} path={path} element={home} />),
      ];
  return (
    <Routes>
      <Route path="/setup" element={home} />
      {SHARED.map(([path, element]) => <Route key={path} path={path} element={element()} />)}
      {typed}
      <Route path="/*" element={<Root />} />
    </Routes>
  );
}
