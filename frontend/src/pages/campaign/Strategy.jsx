import { useStrategy } from "@/api/hooks";
import StrategyNotes from "./StrategyNotes";
import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";
import { SlottedHeader } from "@/components/layout/AppPage";

export default function Strategy({ campaign }) {
  const strategy = useStrategy(campaign.id);
  return (
    <>
      <SlottedHeader context="Plan" title="Strategy" sub="Your next moves, computed from your own data." />
      {strategy.isLoading && <LoadingText />}
      <ErrorText error={strategy.error} />
      {strategy.data && <StrategyNotes notes={strategy.data.notes} wide={false} />}
    </>
  );
}
