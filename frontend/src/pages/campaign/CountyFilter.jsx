import { useConstituencies, useCounties } from "@/api/hooks";
import { PlaceSelects } from "@/components/PlaceCascade";

/** A national seat's county and constituency filter; `place` is { county, constituency }. */
export default function CountyFilter({ place, onChange }) {
  const counties = useCounties().data || [];
  const constituencies = useConstituencies(place.county).data || [];
  return (
    <div className="flex flex-wrap gap-3">
      <PlaceSelects level="constituency" place={place} lists={{ counties, constituencies }} onChange={({ county, constituency }) => onChange({ county, constituency })} />
    </div>
  );
}
