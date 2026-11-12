import { Button } from "@/components/ui/button";
import { unsent } from "@/lib/draft";
import { ErrorText } from "@/components/ui/error-text";
import { Notice } from "@/components/ui/notice";

/** Why a field form didn't send. With no network, the entry is kept and can be sent again. */
export default function SendError({ error, onRetry, pending }) {
  if (!error) return null;
  if (!unsent(error)) return <ErrorText error={error} />;
  return (
    <Notice role="alert" className="flex flex-col gap-3 p-4">
      <p className="text-ui"><strong>Not sent: no network.</strong> Your entry is kept on this phone. Try again when you have signal.</p>
      <Button variant="quiet" className="self-start" disabled={pending} onClick={onRetry}>{pending ? "Sending…" : "Try again"}</Button>
    </Notice>
  );
}
