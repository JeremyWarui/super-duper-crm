import { PageTitle } from "../../components/ui";
import { useMobilizers, useStrategy } from "../../api/hooks";
import { ErrorMsg, Loading } from "./controls";
import { assignerFor } from "./helpers";
import UnitRegister from "./UnitRegister";

export default function Units({ campaign, role, onModal }) {
  const strategy = useStrategy(campaign.id);
  const mobilizers = useMobilizers(campaign.id);
  const assign = assignerFor(role, onModal);
  if (strategy.isLoading) return <Loading />; if (strategy.error) return <ErrorMsg error={strategy.error} />;
  return (<><PageTitle title={role === "candidate" ? "Ward performance" : "Wards"} sub="Win number, progress and coverage per unit." /><UnitRegister units={strategy.data.units} mobilizers={mobilizers.data || []} onAssign={assign} /></>);
}
