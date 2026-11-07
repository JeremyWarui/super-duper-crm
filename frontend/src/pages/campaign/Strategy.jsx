import { useStrategy } from "@/api/hooks";
import StrategyNotes from "./StrategyNotes";
import WsHeader, { KitLoading } from "./WsHeader";
import { ErrorText } from "@/components/ui/error-text";

export default function Strategy({ campaign }) {
  const strategy = useStrategy(campaign.id);
  return (
    <>
      <WsHeader context="Plan" title="Strategy" sub="Your next moves, computed from your own data." />
      {strategy.isLoading && <KitLoading />}
      <ErrorText error={strategy.error} />
      {strategy.data && <StrategyNotes notes={strategy.data.notes} wide={false} />}
    </>
  );
}
