// The public site's frame: the party's logo, name and menu above, its contacts below.
import { Link, NavLink } from "react-router-dom";
import { useParty } from "../api/hooks";
import { homeOf } from "../lib/home";
import { partyColours } from "../pages/public/colours";
import { useAuth } from "../store/auth";

const MENU = [
  ["/", "Home"],
  ["/about", "About"],
  ["/leadership", "Leadership"],
  ["/manifesto", "Manifesto"],
  ["/news", "News"],
  ["/events", "Events"],
  ["/join-party", "Join"],
];

export default function PublicLayout({ children }) {
  const party = useParty().data;
  const token = useAuth((s) => s.token);
  const user = useAuth((s) => s.user);
  const socials = Object.entries(party?.social_links || {});

  return (
    <div className="site" style={partyColours(party)}>
      <header className="site-header">
        <Link className="site-brand" to="/">
          {party?.logo_url && <img className="site-logo" src={party.logo_url} alt="" />}
          <span>{party?.name || "Party"}</span>
        </Link>
        <nav className="site-nav" aria-label="Site">
          {MENU.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className="site-nav-link">
              {label}
            </NavLink>
          ))}
          <Link className="site-nav-link site-signin" to={token ? homeOf(user) : "/signin"}>
            {token ? "Portal" : "Sign in"}
          </Link>
        </nav>
      </header>
      <main className="site-main">{children}</main>
      <footer className="site-footer">
        <div className="site-footer-name">{party?.name}</div>
        {party?.address && <div>{party.address}</div>}
        {party?.contact_phone && <div>{party.contact_phone}</div>}
        {party?.contact_email && (
          <a className="site-link" href={`mailto:${party.contact_email}`}>
            {party.contact_email}
          </a>
        )}
        {socials.length > 0 && (
          <div className="site-socials">
            {socials.map(([name, url]) => (
              <a key={name} className="site-link" href={url} target="_blank" rel="noreferrer">
                {name}
              </a>
            ))}
          </div>
        )}
      </footer>
    </div>
  );
}
