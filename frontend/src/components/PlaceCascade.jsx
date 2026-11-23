// County, then constituency, ward and polling station: choosing one clears those below it.
import { useState } from "react";
import { usePlaceLists } from "@/api/hooks";
import { FilterSelect } from "@/components/ui/input";

const LEVELS = ["county", "constituency", "ward", "centre"];
const LABEL = { county: "County", constituency: "Constituency", ward: "Ward", centre: "Polling station" };
const MANY = { county: "counties", constituency: "constituencies", ward: "wards", centre: "centres" };

/** A place with nothing chosen. */
export const NO_PLACE = { county: "", constituency: "", ward: "" };

/**
 * The selects down to `level`, filled from `lists` ({ counties, constituencies, wards, centres }); `onChange`
 * gets the whole place. `blank(level)` reads each empty option; `labelled` shows labels above.
 */
export function PlaceSelects({ place, onChange, lists, level = "ward", blank = (lv) => `All ${MANY[lv]}`, labelled, className, ...rest }) {
  const shown = LEVELS.slice(0, LEVELS.indexOf(level) + 1);
  return shown.map((lv, i) => (
    <FilterSelect
      key={lv}
      label={LABEL[lv]}
      blank={blank(lv)}
      value={place[lv] ?? ""}
      options={lists[MANY[lv]]}
      disabled={i > 0 && !place[shown[i - 1]]}
      labelled={labelled}
      className={className}
      onChange={(id) => onChange({ ...place, [lv]: id, ...Object.fromEntries(LEVELS.slice(i + 1).map((k) => [k, ""])) })}
      {...rest}
    />
  ));
}

/** The places down to `level`; takes every prop PlaceSelects does but `lists`. */
export default function PlaceCascade(props) {
  return <PlaceSelects lists={usePlaceLists(props.place, props.level)} {...props} />;
}

/** County, constituency, then ward, for a national seat's forms; `onChange` gets the ward id. */
export function WardCascade({ onChange, ...rest }) {
  const [place, setPlace] = useState(NO_PLACE);
  return <PlaceCascade place={place} level="ward" blank={(lv) => `Pick your ${lv}`} onChange={(p) => { setPlace(p); onChange(p.ward); }} {...rest} />;
}
