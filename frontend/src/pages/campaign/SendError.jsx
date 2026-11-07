import { Button } from "@/components/ui/button";
import { unsent } from "@/lib/draft";
import { ErrorText } from "@/components/ui/error-text";

/** Why a field form didn't send. With no network, the entry is kept and can be sent again. */
export default function SendError({ error, onRetry, pending }) {
  if (!error) return null;
  if (!unsent(error)) return <ErrorText error={error} />;
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-lg border border-[#F2D98A] bg-warn p-4 text-warn-foreground">
      <p className="text-ui"><strong>Not sent: no network.</strong> Your entry is kept on this phone. Try again when you have signal.</p>
      <Button shape="rounded" variant="quiet" className="self-start" disabled={pending} onClick={onRetry}>{pending ? "Sending…" : "Try again"}</Button>
    </div>
  );
}
