import { Button } from "./ui";

export default function PortalLayout({
  brand,
  title,
  meta,
  user,
  navLabel,
  nav,
  page,
  onSelect,
  onLogout,
  children,
}) {
  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="mx-auto flex flex-wrap items-center justify-between gap-3 topbar-inner">
          <div className="flex items-center gap-3 topbar-identity"><div className="brand">{brand}</div><div className="topbar-divider" /><div><div className="topbar-campaign">{title}</div><div className="topbar-meta">{meta}</div></div></div>
          <div className="flex items-center gap-3"><span className="topbar-user">{user}</span><Button onClick={onLogout}>Sign out</Button></div>
        </div>
      </div>

      <div className="mx-auto layout">
        <nav className="sidebar">
          <div className="sidebar-label">{navLabel}</div>
          <div className="nav">
            {nav.map(([key, label]) => <button key={key} type="button" aria-current={page === key ? "page" : undefined} onClick={() => onSelect(key)} className={`nav-item ${page === key ? "nav-item-active" : ""}`.trim()}>{label}</button>)}
          </div>
        </nav>

        <main className="main">
          {children}
        </main>
      </div>
    </div>
  );
}
