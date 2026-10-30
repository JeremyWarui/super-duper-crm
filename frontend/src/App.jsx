// The signed-in campaign app: routes `/campaign/:page` and the shell around each page.
import { useState } from "react";
import { Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "./store/auth";
import { useCampaigns } from "./api/hooks";
import PortalLayout from "./components/PortalLayout";
import NoCampaign from "./components/NoCampaign";
import { ErrorMsg, Loading } from "./pages/campaign/controls";
import { NAV, ROLE_LABEL } from "./pages/campaign/helpers";
import CampaignModal from "./pages/campaign/CampaignModal";
import Overview from "./pages/campaign/Overview";
import Units from "./pages/campaign/Units";
import Strategy from "./pages/campaign/Strategy";
import Targets from "./pages/campaign/Targets";
import Team from "./pages/campaign/Team";
import Mobilizers from "./pages/campaign/Mobilizers";
import Supporters from "./pages/campaign/Supporters";
import Events from "./pages/campaign/Events";
import Register from "./pages/campaign/Register";
import Payments from "./pages/campaign/Payments";

// One page per NAV key.
const PAGES = {
  overview: Overview,
  units: Units,
  strategy: Strategy,
  targets: Targets,
  team: Team,
  mobilizers: Mobilizers,
  supporters: Supporters,
  events: Events,
  payments: Payments,
  register: Register,
  myevents: (props) => <Events {...props} mine />,
  mysupporters: (props) => <Supporters {...props} mine />,
  mypayments: (props) => <Payments {...props} mine />,
};

function Shell({ campaign, role, nav }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();
  const [modal, setModal] = useState(null);
  const { page } = useParams();
  if (!nav.some(([key]) => key === page)) return <Navigate to={`/campaign/${nav[0][0]}`} replace />;
  const Page = PAGES[page];

  return (
    <>
      <PortalLayout
        brand={<>MZIGO<span className="brand-mark">·</span>CRM</>}
        title={campaign.title}
        meta={[campaign.candidate_name && `for ${campaign.candidate_name}`, campaign.seat, campaign.area_name].filter(Boolean).join(" · ")}
        user={`${user?.full_name || user?.username} · ${ROLE_LABEL[role]}`}
        navLabel={ROLE_LABEL[role].toUpperCase()}
        nav={nav}
        page={page}
        onSelect={(key) => navigate(`/campaign/${key}`)}
        onLogout={logout}
      >
        <Page campaign={campaign} role={role} onModal={setModal} />
      </PortalLayout>
      <CampaignModal modal={modal} campaign={campaign} role={role} onClose={() => setModal(null)} />
    </>
  );
}

export default function App() {
  const role = useAuth((s) => s.user?.role);
  const nav = NAV[role];
  const campaigns = useCampaigns();
  const campaign = (campaigns.data || [])[0];

  if (!nav) return <NoCampaign />;
  if (campaigns.isLoading) return <Loading />;
  if (campaigns.error) return <ErrorMsg error={campaigns.error} />;
  if (!campaign) return <div className="not-on-campaign">You are not on a campaign yet.</div>;

  return (
    <Routes>
      <Route path="campaign/:page" element={<Shell campaign={campaign} role={role} nav={nav} />} />
      <Route path="*" element={<Navigate to={`/campaign/${nav[0][0]}`} replace />} />
    </Routes>
  );
}
