// The signed-in party portal: routes `/party/*` and the shell around each page.
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../store/auth";
import { useParty } from "../../api/hooks";
import PortalLayout from "../../components/PortalLayout";
import Aspirants from "./Aspirants";
import Finance from "./Finance";
import Members from "./Members";
import Volunteers from "./Volunteers";
import { PARTY_ROLE_LABEL } from "./helpers";

// Each page and the office that opens it; the superuser opens every one.
const PAGES = [
  ["members", "Members", "membership_officer", <Members key="members" />],
  ["volunteers", "Volunteers", "membership_officer", <Volunteers key="volunteers" />],
  ["aspirants", "Aspirants", "nominations_officer", <Aspirants key="aspirants" />],
  ["finance", "Finance", "finance_officer", <Finance key="finance" />],
];

export default function Portal() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const party = useParty().data;
  const roles = user?.party_roles || [];
  const pages = PAGES.filter(([, , office]) => user?.is_superuser || roles.includes(office));
  const nav = [
    ...pages.map(([key, label]) => [key, label]),
    ...(user?.is_superuser ? [["console", "Console"]] : []),
  ];
  const office = user?.is_superuser
    ? "Party super admin"
    : roles.map((r) => PARTY_ROLE_LABEL[r] || r).join(", ");
  const current = pages.find(([key]) => pathname.startsWith(`/party/${key}`))?.[0] ?? pages[0]?.[0];

  return (
    <PortalLayout
      brand={party?.short_name || party?.name || "Party"}
      title={party?.name || ""}
      meta="Party portal"
      user={`${user?.full_name || user?.username} · ${office}`}
      navLabel="PARTY"
      nav={nav}
      page={pages.length ? current : null}
      onSelect={(key) => navigate(key === "console" ? "/console" : `/party/${key}`)}
      onLogout={logout}
    >
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
    </PortalLayout>
  );
}
