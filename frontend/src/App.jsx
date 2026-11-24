// The signed-in campaign app: routes `/campaign/:page` and the shell around each page.
import { Suspense, lazy, useMemo, useState } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppPage } from "@/components/layout/AppPage";
import { CrmTopBar } from "@/components/layout/CrmTopBar";
import { useBranding } from "@/theme/branding";
import { useAuth } from "./store/auth";
import { useCampaigns } from "./api/hooks";
import { NoCampaign } from "./components/SignedInNotice";
import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";
import { navFor, pagesOf, unitOf } from "./pages/campaign/helpers";
import { ROLE_LABEL } from "@/lib/labels";
import {
  AccessFooter, AreaPicker, SeatCard, WorkspaceAlerts, WorkspaceBrand, WorkspaceHelp, WorkspaceSearch,
} from "./pages/campaign/WorkspaceShell";
import { AreaContext, ICONS, useShellData } from "./pages/campaign/shell";
import CampaignModal from "./pages/campaign/CampaignModal";
import Overview from "./pages/campaign/Overview";
import Calls from "./pages/campaign/Calls";
import CallAlerts from "./components/CallAlerts";
import Units from "./pages/campaign/Units";
import Strategy from "./pages/campaign/Strategy";
import Targets from "./pages/campaign/Targets";
import Team from "./pages/campaign/Team";
import Mobilizers from "./pages/campaign/Mobilizers";
import Supporters from "./pages/campaign/Supporters";
import Events from "./pages/campaign/Events";
import Register from "./pages/campaign/Register";
import Payments from "./pages/campaign/Payments";
import Contributions from "./pages/campaign/Contributions";
import Volunteers from "./pages/campaign/Volunteers";
import Website from "./pages/campaign/Website";
import Settings from "./pages/campaign/Settings";
import Signups from "./pages/campaign/Signups";
import Agents from "./pages/campaign/Agents";
import MyCentre from "./pages/campaign/MyCentre";
import Assignments from "./pages/campaign/Assignments";
import Messages from "./pages/campaign/Messages";
import Privacy from "./pages/campaign/Privacy";
import ClosedNote from "./pages/campaign/ClosedNote";
import FieldTabs from "./pages/campaign/FieldTabs";
import { useMedia } from "./lib/useMedia";
import { displayName } from "@/lib/format";

// The call page loads LiveKit only when someone joins a call.
const Meet = lazy(() => import("./pages/Meet"));

// Roles that work from a phone get a tab bar there.
const FIELD_ROLES = ["mobilizer", "agent"];

// One page per NAV key.
export const PAGES = {
  overview: Overview,
  units: Units,
  strategy: Strategy,
  targets: Targets,
  calls: Calls,
  team: Team,
  mobilizers: Mobilizers,
  supporters: Supporters,
  events: Events,
  payments: Payments,
  contributions: Contributions,
  volunteers: Volunteers,
  website: Website,
  settings: Settings,
  signups: Signups,
  agents: Agents,
  mycentre: MyCentre,
  assignments: Assignments,
  messages: Messages,
  privacy: Privacy,
  register: Register,
  myevents: (props) => <Events {...props} mine />,
  mysupporters: (props) => <Supporters {...props} mine />,
  mypayments: (props) => <Payments {...props} mine />,
};

function Shell({ campaign, role, where }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const { siteName } = useBranding();
  const [modal, setModal] = useState(null);
  const [area, setArea] = useState(null);
  const { page } = useParams();
  const data = useShellData(campaign, role);
  const phone = useMedia("(max-width: 767px)");
  const areaValue = useMemo(() => ({ area, setArea, wards: data.wards }), [area, data.wards]);
  const pages = pagesOf(role, where);
  const current = pages.find(([key]) => key === page);
  if (!current) return <Navigate to={`/campaign/${pages[0][0]}`} replace />;
  const Page = PAGES[page];
  const groups = navFor(role, where).map((g) => ({
    label: g.label,
    items: g.items.map(([key, label]) => ({ label, to: `/campaign/${key}`, icon: ICONS[key] })),
  }));

  return (
    <AreaContext.Provider value={areaValue}>
      <AppLayout
        tone="light"
        groups={groups}
        brand={<WorkspaceBrand name={siteName} />}
        card={<SeatCard campaign={campaign} winNumber={data.strategy?.win_number} />}
        footer={<AccessFooter role={role} wards={data.wards} />}
        topBar={(bar) => (
          <CrmTopBar
            {...bar}
            search={<WorkspaceSearch data={data} role={role} />}
            tools={<><AreaPicker /><WorkspaceAlerts data={data} role={role} /><WorkspaceHelp /></>}
          />
        )}
        slotHeaders
        rootLabel="Campaign workspace"
        rootPath="/campaign"
        user={{ name: displayName(user), role: ROLE_LABEL[role] }}
        onSignOut={logout}
      >
        <AppPage crumb={current[1]}>
          {campaign.closed_at && <ClosedNote />}
          <CallAlerts />
          <Page campaign={campaign} role={role} onModal={setModal} />
          {modal && <CampaignModal modal={modal} campaign={campaign} role={role} onClose={() => setModal(null)} />}
        </AppPage>
        {phone && FIELD_ROLES.includes(role) && <FieldTabs items={groups.flatMap((g) => g.items)} />}
      </AppLayout>
    </AreaContext.Provider>
  );
}

export default function App() {
  const role = useAuth((s) => s.user?.role);
  const campaigns = useCampaigns();
  const campaign = (campaigns.data || [])[0];

  if (!pagesOf(role).length) return <NoCampaign />;
  if (campaigns.isLoading) return <div className="p-10"><LoadingText /></div>;
  if (campaigns.error) return <div className="p-10"><ErrorText error={campaigns.error} /></div>;
  if (!campaign) return <p className="p-10 text-muted-foreground">You are not on a campaign yet.</p>;
  const where = { byCentre: unitOf(campaign).byCentre };
  const pages = pagesOf(role, where);

  return (
    <Routes>
      <Route path="campaign/:page" element={<Shell campaign={campaign} role={role} where={where} />} />
      <Route path="meet/:meetingId" element={<Suspense fallback={<div className="p-10"><LoadingText /></div>}><Meet /></Suspense>} />
      <Route path="*" element={<Navigate to={`/campaign/${pages[0][0]}`} replace />} />
    </Routes>
  );
}
