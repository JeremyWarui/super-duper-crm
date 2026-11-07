import { usePartyPlaceLists } from "../../api/hooks";
import { FilterSelect } from "../../components/ui";

/** County, constituency and ward filters; choosing one level clears those below it, and `onChange` gets the whole place. */
export default function PlaceFilters({ place, onChange }) {
  const { counties, constituencies, wards } = usePartyPlaceLists(place);
  return (
    <>
      <FilterSelect label="County" blank="All counties" value={place.county} options={counties} onChange={(county) => onChange({ county, constituency: "", ward: "" })} />
      <FilterSelect label="Constituency" blank="All constituencies" value={place.constituency} options={constituencies} disabled={!place.county} onChange={(constituency) => onChange({ ...place, constituency, ward: "" })} />
      <FilterSelect label="Ward" blank="All wards" value={place.ward} options={wards} disabled={!place.constituency} onChange={(ward) => onChange({ ...place, ward })} />
    </>
  );
}
