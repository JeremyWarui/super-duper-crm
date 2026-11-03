// The signed-in party portal: routes `/party/*` and the shell around each page.
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppPage } from "@/components/layout/AppPage";
import { useAuth } from "../../store/auth";
import { homeOf } from "../../lib/home";
import Legacy from "../../components/Legacy";
import Aspirants from "./Aspirants";
import Branches from "./Branches";
import Dashboard from "./Dashboard";
import Finance from "./Finance";
import Members from "./Members";
import Volunteers from "./Volunteers";
import Website from "./Website";
import { PARTY_ROLE_LABEL } from "./helpers";

// Each page and the office that opens it; the superuser opens every one, and only the
// superuser opens those marked "superuser".
const PAGES = [
  ["dashboard", "Dashboard", "superuser", <Dashboard key="dashboard" />],
  ["members", "Members", "membership_officer", <Members key="members" />],
  ["volunteers", "Volunteers", "membership_officer", <Volunteers key="volunteers" />],
  ["aspirants", "Aspirants", "nominations_officer", <Aspirants key="aspirants" />],
  ["finance", "Finance", "finance_officer", <Finance key="finance" />],
  ["branches", "Branches", "superuser", <Branches key="branches" />, { kit: true, context: "Party structure", title: "Branches" }],
  ["website", "Website", "superuser", <Website key="website" />],
];

/** The party CRM's sidebar for a login: the pages its offices open, and the console for the superuser. */
export function partyNav(user) {
  const roles = user?.party_roles || [];
  return [
    ...PAGES.filter(([, , office]) => user?.is_superuser || roles.includes(office)).map(([key, label]) => ({ label, to: `/party/${key}` })),
    ...(user?.is_superuser ? [{ label: "Console", to: "/console" }] : []),
  ];
}

export function officeOf(user) {
  return user?.is_superuser
    ? "Party super admin"
    : (user?.party_roles || []).map((r) => PARTY_ROLE_LABEL[r] || r).join(", ");
}

/** The party CRM's frame around one page; a page not yet on the kit stays inside Legacy. */
export function PartyShell({ crumb, page, children }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  return (
    <AppLayout
      tone="dark"
      nav={partyNav(user)}
      rootLabel="Party CRM"
      rootPath={homeOf(user)}
      subtitle={officeOf(user)}
      user={{ name: user?.full_name || user?.username || "", role: officeOf(user) }}
      onSignOut={logout}
    >
      {page?.kit ? (
        <AppPage crumb={crumb} context={page.context} title={page.title}>{children}</AppPage>
      ) : (
        <AppPage crumb={crumb}>
          <Legacy>{children}</Legacy>
        </AppPage>
      )}
    </AppLayout>
  );
}

export default function Portal() {
  const user = useAuth((s) => s.user);
  const { pathname } = useLocation();
  const roles = user?.party_roles || [];
  const pages = PAGES.filter(([, , office]) => user?.is_superuser || roles.includes(office));
  const current = pages.find(([key]) => pathname.startsWith(`/party/${key}`)) ?? pages[0];

  return (
    <PartyShell crumb={current?.[1] || "Party CRM"} page={current?.[4]}>
      {pages.length ? (
        <Routes>
          {pages.map(([key, , , element]) => (
            <Route key={key} path={`party/${key}`} element={element} />
          ))}
          <Route path="*" element={<Navigate to={`/party/${pages[0][0]}`} replace />} />
        </Routes>
      ) : (
        <div className="empty-row">There is nothing for your office here yet.</div>
      )}
    </PartyShell>
  );
}
