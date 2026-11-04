// The party's logo and name, as every header shows them, from the website settings.
import { useEffect } from "react";
import { useSite } from "../api/hooks";

export default function PartyBrand({ className = "", label }) {
  const party = useSite();
  const p = party.data;
  const name = p?.name || "";

  useEffect(() => {
    if (name) document.title = label ? `${name} · ${label}` : name;
  }, [name, label]);

  return (
    <span className={`party-brand ${className}`.trim()}>
      {p?.logo_url ? (
        <img src={p.logo_url} alt="" className="party-brand-logo" />
      ) : (
        <span className="party-brand-mark" aria-hidden="true">{name.slice(0, 1)}</span>
      )}
      <span className="party-brand-name">{name}</span>
      {label && <span className="party-brand-label">{label}</span>}
    </span>
  );
}
