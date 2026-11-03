// The root of a page not yet moved onto the UI kit; index.css styles only what is inside it.
import { useParty } from "../api/hooks";
import { partyColours } from "../pages/public/colours";

export default function Legacy({ children }) {
  return <div className="legacy">{children}</div>;
}

/** A public page not yet moved, inside the kit's website frame. */
export function LegacySite({ children }) {
  const party = useParty().data;
  return (
    <div className="legacy" style={partyColours(party)}>
      <div className="site-main">{children}</div>
    </div>
  );
}
