// The signed-in campaign app: routes `/campaign/:page` and the shell around each page.
import { useMemo, useState } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppPage } from "@/components/layout/AppPage";
import { WsTopBar } from "@/components/layout/WsTopBar";
import { useBranding } from "@/theme/branding";
import { useAuth } from "./store/auth";
import { useCampaigns } from "./api/hooks";
import Legacy from "./components/Legacy";
import NoCampaign from "./components/NoCampaign";
import { ErrorMsg, Loading } from "./pages/campaign/controls";
import { ROLE_LABEL, navFor, pagesOf } from "./pages/campaign/helpers";
import { useInstall } from "./app/site";
import {
  AccessFooter, AreaPicker, SeatCard, WorkspaceAlerts, WorkspaceBrand, WorkspaceHelp, WorkspaceSearch,
} from "./pages/campaign/WorkspaceShell";
import { AreaContext, ICONS, useShellData } from "./pages/campaign/shell";
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
import Website from "./pages/campaign/Website";
import Settings from "./pages/campaign/Settings";
import Recruitment from "./pages/campaign/Recruitment";
import Members from "./pages/campaign/Members";
import Signups from "./pages/campaign/Signups";
import Agents from "./pages/campaign/Agents";
import MyCentre from "./pages/campaign/MyCentre";
import Assignments from "./pages/campaign/Assignments";
import Messages from "./pages/campaign/Messages";
import PartyFeed from "./pages/campaign/PartyFeed";
import Privacy from "./pages/campaign/Privacy";
import ClosedNote from "./pages/campaign/ClosedNote";
import FieldTabs from "./pages/campaign/FieldTabs";
import { useMedia } from "./lib/useMedia";

// Pages built on the UI kit, which render outside the legacy stylesheet.
// Roles that work from a phone get a tab bar there.
const FIELD_ROLES = ["mobilizer", "agent"];

export const KIT_PAGES = new Set(["overview", "strategy", "targets", "units", "events", "myevents", "mobilizers", "supporters", "mysupporters", "payments", "mypayments", "team", "volunteers", "signups", "agents", "mycentre", "assignments", "messages", "register", "website", "settings", "recruitment", "members", "party", "privacy"]);

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
  website: Website,
  settings: Settings,
  recruitment: Recruitment,
  members: Members,
  signups: Signups,
  agents: Agents,
  mycentre: MyCentre,
  assignments: Assignments,
  messages: Messages,
  party: PartyFeed,
  privacy: Privacy,
  register: Register,
  myevents: (props) => <Events {...props} mine />,
  mysupporters: (props) => <Supporters {...props} mine />,
  mypayments: (props) => <Payments {...props} mine />,
};

function Shell({ campaign, role, where }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const { partyName } = useBranding();
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
        brand={<WorkspaceBrand name={partyName} />}
        card={<SeatCard campaign={campaign} winNumber={data.strategy?.win_number} />}
        footer={<AccessFooter role={role} wards={data.wards} />}
        topBar={(bar) => (
          <WsTopBar
            {...bar}
            search={<WorkspaceSearch data={data} role={role} />}
            tools={<><AreaPicker /><WorkspaceAlerts data={data} role={role} /><WorkspaceHelp /></>}
          />
        )}
        slotHeaders
        rootLabel="Campaign workspace"
        rootPath="/campaign"
        user={{ name: user?.full_name || user?.username || "", role: ROLE_LABEL[role] }}
        onSignOut={logout}
      >
        <AppPage crumb={current[1]}>
          {campaign.closed_at && <ClosedNote />}
          {KIT_PAGES.has(page) ? (
            <>
              <Page campaign={campaign} role={role} onModal={setModal} />
              {modal && <Legacy bare><CampaignModal modal={modal} campaign={campaign} role={role} onClose={() => setModal(null)} /></Legacy>}
            </>
          ) : (
            <Legacy>
              <Page campaign={campaign} role={role} onModal={setModal} />
              <CampaignModal modal={modal} campaign={campaign} role={role} onClose={() => setModal(null)} />
            </Legacy>
          )}
        </AppPage>
        {phone && FIELD_ROLES.includes(role) && <FieldTabs items={groups.flatMap((g) => g.items)} />}
      </AppLayout>
    </AreaContext.Provider>
  );
}

export default function App() {
  const role = useAuth((s) => s.user?.role);
  const install = useInstall();
  const campaigns = useCampaigns();
  const campaign = (campaigns.data || [])[0];

  if (!pagesOf(role).length) return <Legacy><NoCampaign /></Legacy>;
  if (campaigns.isLoading) return <Legacy><Loading /></Legacy>;
  if (campaigns.error) return <Legacy><ErrorMsg error={campaigns.error} /></Legacy>;
  if (!campaign) return <Legacy><div className="not-on-campaign">You are not on a campaign yet.</div></Legacy>;
  const where = { aspirant: install.aspirant, partyWorkspace: campaign.kind === "party", hosted: campaign.kind === "hosted", byCentre: campaign.operational_grain === "centre" };
  const pages = pagesOf(role, where);

  return (
    <Routes>
      <Route path="campaign/:page" element={<Shell campaign={campaign} role={role} where={where} />} />
      <Route path="*" element={<Navigate to={`/campaign/${pages[0][0]}`} replace />} />
    </Routes>
  );
}
