// The signed-in party portal: routes `/party/*` and the shell around each page.
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../store/auth";
import { useParty } from "../../api/hooks";
import PortalLayout from "../../components/PortalLayout";
import Members from "./Members";
import Volunteers from "./Volunteers";
import { PARTY_ROLE_LABEL } from "./helpers";

export default function Portal() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const party = useParty().data;
  const roles = user?.party_roles || [];
  const nav = roles.includes("membership_officer") ? [["members", "Members"], ["volunteers", "Volunteers"]] : [];
  const office = roles.map((r) => PARTY_ROLE_LABEL[r] || r).join(", ");

  return (
    <PortalLayout
      brand={party?.short_name || party?.name || "Party"}
      title={party?.name || ""}
      meta="Party portal"
      user={`${user?.full_name || user?.username} · ${office}`}
      navLabel="PARTY"
      nav={nav}
      page={nav.length ? (pathname.startsWith("/party/volunteers") ? "volunteers" : "members") : null}
      onSelect={(key) => navigate(`/party/${key}`)}
      onLogout={logout}
    >
      {nav.length ? (
        <Routes>
          <Route path="party/members" element={<Members />} />
          <Route path="party/volunteers" element={<Volunteers />} />
          <Route path="*" element={<Navigate to="/party/members" replace />} />
        </Routes>
      ) : (
        <div className="empty-row">There is nothing for your office here yet.</div>
      )}
    </PortalLayout>
  );
}
