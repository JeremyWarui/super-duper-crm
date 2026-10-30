import { PageTitle } from "../../components/ui";
import { useMobilizers, useStrategy } from "../../api/hooks";
import { ErrorMsg, Loading } from "./controls";
import { assignerFor } from "./helpers";
import TallyHero from "./TallyHero";
import UnitRegister from "./UnitRegister";
import StrategyPanel from "./StrategyPanel";

export default function Overview({ campaign, role, onModal }) {
  const strategy = useStrategy(campaign.id);
  const mobilizers = useMobilizers(campaign.id);
  const assign = assignerFor(role, onModal);
  if (strategy.isLoading) return <Loading />; if (strategy.error) return <ErrorMsg error={strategy.error} />;
  return (<><PageTitle title="Overview" sub={role === "candidate" ? "Where the campaign stands today." : "Your command view of the seat."} />
    <div className="overview-stack">
      <TallyHero s={strategy.data} />
      <div className="grid gap-5 overview-grid">
        <UnitRegister units={strategy.data.units} mobilizers={mobilizers.data || []} onAssign={assign} />
        <StrategyPanel notes={strategy.data.notes} />
      </div>
    </div></>);
}
