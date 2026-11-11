import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";

/** A whole site page's loading line, or the first error among `queries`; null once none is loading or failed. */
export function pageState(...queries) {
  if (queries.some((q) => q.isLoading)) return <div className="site-container py-12"><LoadingText /></div>;
  const failed = queries.find((q) => q.error);
  return failed ? <div className="site-container py-12"><ErrorText error={failed.error} /></div> : null;
}
