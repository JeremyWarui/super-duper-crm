// The signed-in campaign app: routes `/campaign/:page` and the shell around each page.
import { useState } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppPage } from "@/components/layout/AppPage";
import { useBranding } from "@/theme/branding";
import { useAuth } from "./store/auth";
import { useCampaigns } from "./api/hooks";
import AccessBanner from "./components/AccessBanner";
import Legacy from "./components/Legacy";
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
import Volunteers from "./pages/campaign/Volunteers";

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
  volunteers: Volunteers,
  register: Register,
  myevents: (props) => <Events {...props} mine />,
  mysupporters: (props) => <Supporters {...props} mine />,
  mypayments: (props) => <Payments {...props} mine />,
};

function Shell({ campaign, role, nav }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const { partyName } = useBranding();
  const [modal, setModal] = useState(null);
  const { page } = useParams();
  const current = nav.find(([key]) => key === page);
  if (!current) return <Navigate to={`/campaign/${nav[0][0]}`} replace />;
  const Page = PAGES[page];

  return (
    <AppLayout
      tone="light"
      nav={nav.map(([key, label]) => ({ label, to: `/campaign/${key}` }))}
      rootLabel="Campaign"
      rootPath="/campaign"
      eyebrow={[partyName, "Campaign"].filter(Boolean).join(" · ")}
      title={campaign.title}
      subtitle={[campaign.candidate_name && `for ${campaign.candidate_name}`, campaign.seat, campaign.area_name].filter(Boolean).join(" · ")}
      user={{ name: user?.full_name || user?.username || "", role: ROLE_LABEL[role] }}
      onSignOut={logout}
    >
      <AppPage crumb={current[1]}>
        <Legacy>
          <AccessBanner role={role} />
          <Page campaign={campaign} role={role} onModal={setModal} />
          <CampaignModal modal={modal} campaign={campaign} role={role} onClose={() => setModal(null)} />
        </Legacy>
      </AppPage>
    </AppLayout>
  );
}

export default function App() {
  const role = useAuth((s) => s.user?.role);
  const nav = NAV[role];
  const campaigns = useCampaigns();
  const campaign = (campaigns.data || [])[0];

  if (!nav) return <Legacy><NoCampaign /></Legacy>;
  if (campaigns.isLoading) return <Legacy><Loading /></Legacy>;
  if (campaigns.error) return <Legacy><ErrorMsg error={campaigns.error} /></Legacy>;
  if (!campaign) return <Legacy><div className="not-on-campaign">You are not on a campaign yet.</div></Legacy>;

  return (
    <Routes>
      <Route path="campaign/:page" element={<Shell campaign={campaign} role={role} nav={nav} />} />
      <Route path="*" element={<Navigate to={`/campaign/${nav[0][0]}`} replace />} />
    </Routes>
  );
}
