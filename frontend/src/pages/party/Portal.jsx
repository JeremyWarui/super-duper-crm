// The signed-in party portal: routes `/party/*` and the shell around each page.
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppPage } from "@/components/layout/AppPage";
import { ConsoleTools } from "@/components/layout/ConsoleTools";
import { useInstall } from "@/app/site";
import { useCopy } from "@/copy";
import { useAuth } from "../../store/auth";
import { homeOf } from "../../lib/home";
import Legacy from "../../components/Legacy";
import DataRequests from "../../components/DataRequests";
import Aspirants from "./Aspirants";
import Branches from "./Branches";
import Dashboard from "./Dashboard";
import Members from "./Members";
import PaymentsIn from "./PaymentsIn";
import Messages from "./Messages";
import Volunteers from "./Volunteers";
import Website from "./Website";
import { PARTY_ROLE_LABEL } from "./helpers";

// Each page and the office that opens it; the superuser opens every one, and only the
// superuser opens those marked "superuser".
const PAGES = [
  ["dashboard", "Dashboard", "superuser", <Dashboard key="dashboard" />],
  ["members", "Members", "membership_officer", <Members key="members" />],
  ["volunteers", "Volunteers", "membership_officer", <Volunteers key="volunteers" />],
  ["data-requests", "Data requests", "membership_officer", <DataRequests key="data-requests" />, { kit: true, context: "Personal data", title: "Data requests" }],
  ["aspirants", "Aspirants", "nominations_officer", <Aspirants key="aspirants" />],
  ["payments-in", "Payments in", "nominations_officer", <PaymentsIn key="payments-in" />, { kit: true, context: "Money", title: "Payments in" }],
  ["messages", "Messages", "comms_officer", <Messages key="messages" />, { kit: true, context: "Reach members", title: "Messages" }],
  ["branches", "Branches", "membership_officer", <Branches key="branches" />, { kit: true, context: "Party structure", title: "Branches" }],
  ["website", "Website", "superuser", <Website key="website" />, { kit: true, context: "Website content", title: "Edit the party website" }],
];

/**
 * The sidebar for a login: the pages its offices open, and the console for the superuser.
 * An aspirant installation has no party pages.
 */
export function partyNav(user, { aspirant = false } = {}) {
  const roles = user?.party_roles || [];
  const pages = aspirant ? [] : PAGES.filter(([, , office]) => user?.is_superuser || roles.includes(office));
  return [
    ...pages.map(([key, label]) => ({ label, to: `/party/${key}` })),
    ...(user?.is_superuser ? [{ label: "Console", to: "/console" }] : []),
  ];
}

function officeOf(user, superAdmin) {
  return user?.is_superuser
    ? superAdmin
    : (user?.party_roles || []).map((r) => PARTY_ROLE_LABEL[r] || r).join(", ");
}

/** The party CRM's frame around one page; a page not yet on the kit stays inside Legacy. */
export function PartyShell({ crumb, page, children }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const { aspirant } = useInstall();
  const copy = useCopy();
  const office = officeOf(user, copy.superAdmin);
  return (
    <AppLayout
      tone="dark"
      nav={partyNav(user, { aspirant })}
      rootLabel={copy.consoleRoot}
      rootPath={homeOf(user)}
      subtitle={office}
      user={{ name: user?.full_name || user?.username || "", role: office }}
      onSignOut={logout}
      tools={<ConsoleTools />}
      slotHeaders
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
