// What the party is and how to reach it.
import { useParty } from "../../api/hooks";

export default function About() {
  const party = useParty().data;
  return (
    <section className="site-section">
      <h1 className="site-title">About {party?.short_name || party?.name}</h1>
      {party?.description && <p className="site-text">{party.description}</p>}
      <h2 className="site-section-title">Contact</h2>
      {party?.address && <p className="site-text">{party.address}</p>}
      {party?.contact_phone && <p className="site-text">{party.contact_phone}</p>}
      {party?.contact_email && (
        <a className="site-link" href={`mailto:${party.contact_email}`}>{party.contact_email}</a>
      )}
    </section>
  );
}
