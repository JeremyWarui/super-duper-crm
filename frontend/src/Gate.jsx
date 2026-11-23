import { lazy, Suspense, useRef } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useAuth } from "./store/auth";
import { useCampaigns, useMe } from "./api/hooks";
import { homeOf } from "./lib/home";
import Login from "./components/Login";
import { NoCampaign } from "./components/SignedInNotice";
import Join from "./components/Join";
import Withdraw from "./components/Withdraw";
import { PublicLayout } from "@/components/layout/PublicLayout";
import Events from "./pages/public/Events";
import Home, { About, AgendaPage, Media } from "./pages/public/Home";
import Volunteer from "./pages/public/Volunteer";
import VolunteerWithdraw from "./pages/public/VolunteerWithdraw";
import { useInstall } from "./app/site";
import News from "./pages/public/News";
import Post from "./pages/public/Post";
import ForgotPassword from "./pages/public/ForgotPassword";
import SetPassword from "./pages/public/SetPassword";
import TeamSignup from "./pages/public/TeamSignup";
import Contribute from "./pages/public/Contribute";
import Privacy from "./pages/public/Privacy";
import Unsubscribe from "./pages/public/Unsubscribe";
import Issue from "./pages/public/Issue";
import { LoadingText } from "@/components/ui/loading-text";

/** The whole-page wait while the site settings or a page's code arrive: a spinner mid-screen. */
const waiting = <LoadingText className="min-h-svh py-0" />;

// The signed-in areas load when first opened, so the public site's first load stays small.
const App = lazy(() => import("./App"));
const Admin = lazy(() => import("./components/Admin"));
const Setup = lazy(() => import("./pages/setup/Setup"));

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

// A login on a campaign gets the campaign app; one on none waits to be put on a campaign.
function SignedIn() {
  const campaigns = useCampaigns();
  if (campaigns.isSuccess && campaigns.data.length === 0) return <NoCampaign />;
  return <App />;
}

// A superuser runs the deployment rather than a campaign, so they get the console at /console.
function Inside() {
  useMe();
  const isSuperuser = useAuth((s) => s.user?.is_superuser);
  const { pathname } = useLocation();
  if (isSuperuser) return pathname.startsWith("/console") ? <Admin /> : <Navigate to="/console" replace />;
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
  return token ? <Navigate to={homeOf(user)} replace /> : <Login />;
}

function PostPage() {
  const { id } = useParams();
  return <Post key={id} id={id} />;
}

/** `Page` given the route's `:code`. */
const withCode = (Page) => function CodePage() {
  return <Page code={useParams().code} />;
};
const JoinPage = withCode(Join);
const WithdrawPage = withCode(Withdraw);

const page = (element) => <PublicLayout>{element}</PublicLayout>;

const ROUTES = [
  ["/", () => page(<Home />)],
  ["/about", () => page(<About />)],
  ["/agenda", () => page(<AgendaPage />)],
  ["/media", () => page(<Media />)],
  ["/volunteer", () => page(<Volunteer />)],
  ["/volunteer/withdraw/:code", () => page(<VolunteerWithdraw />)],
  ["/news", () => page(<News />)],
  ["/news/:id", () => page(<PostPage />)],
  ["/events", () => page(<Events />)],
  ["/contribute", () => page(<Contribute />)],
  ["/privacy", () => page(<Privacy />)],
  ["/unsubscribe/:code", () => page(<Unsubscribe />)],
  ["/issues/:id", () => page(<Issue />)],
  ["/signin", () => <SignInPage />],
  ["/forgot-password", () => page(<ForgotPassword />)],
  ["/invite/:token", () => page(<SetPassword />)],
  ["/reset/:token", () => page(<SetPassword />)],
  ["/team/:code", () => page(<TeamSignup />)],
  // An event's QR code opens the sign-up page on its own, without waiting for the site frame.
  ["/join/:code", () => <JoinPage />],
  ["/withdraw/:code", () => page(<WithdrawPage />)],
];

const home = <Navigate to="/" replace />;

// The website, the setup wizard until the installation exists, and the signed-in apps.
export function AppRoutes() {
  const install = useInstall();
  // Latched: a refetch or finishing setup must not swap the wizard out mid-way.
  const settingUp = useRef(false);
  if (install.notSetUp) settingUp.current = true;
  if (settingUp.current) {
    return (
      <Suspense fallback={waiting}>
        <Routes>
          <Route path="/setup" element={<Setup />} />
          <Route path="*" element={<Navigate to="/setup" replace />} />
        </Routes>
      </Suspense>
    );
  }
  return (
    <Suspense fallback={waiting}>
      <Routes>
        <Route path="/setup" element={home} />
        {ROUTES.map(([path, element]) => <Route key={path} path={path} element={element()} />)}
        <Route path="/*" element={<Root />} />
      </Routes>
    </Suspense>
  );
}
