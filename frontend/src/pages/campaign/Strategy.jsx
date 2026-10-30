import { PageTitle } from "../../components/ui";
import { useStrategy } from "../../api/hooks";
import { ErrorMsg, Loading } from "./controls";
import StrategyPanel from "./StrategyPanel";

export default function Strategy({ campaign }) {
  const strategy = useStrategy(campaign.id);
  if (strategy.isLoading) return <Loading />; if (strategy.error) return <ErrorMsg error={strategy.error} />;
  return (<><PageTitle title="Strategy read" sub="Your next moves, computed from your own data." /><StrategyPanel notes={strategy.data.notes} /></>);
}
