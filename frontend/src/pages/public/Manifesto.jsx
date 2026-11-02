// The party's manifesto, and the full document if it has one online.
import { useParty } from "../../api/hooks";

export default function Manifesto() {
  const party = useParty().data;
  return (
    <section className="site-section">
      <h1 className="site-title">Manifesto</h1>
      <p className="site-text">{party?.manifesto_text || "The manifesto will be published here."}</p>
      {party?.manifesto_url && (
        <a className="site-button" href={party.manifesto_url} target="_blank" rel="noreferrer">
          Read the full manifesto
        </a>
      )}
    </section>
  );
}
