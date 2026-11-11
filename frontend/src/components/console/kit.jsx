// Small pieces the console's tabs share.
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Confirm } from "@/components/ui/confirm";
import { Card } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";

const PILL_TONE = { candidate: "tint", superuser: "tint", manager: "stone", mobilizer: "warn", disabled: "bad" };

export const Pill = ({ text }) => <Badge tone={PILL_TONE[text] || "stone"}>{text}</Badge>;

// An inline control: full width on a phone, sharing the row from sm up.
export const INLINE = "w-full sm:w-auto sm:min-w-56 sm:flex-1";

export const Help = ({ children }) => <p className="text-small leading-relaxed text-muted-foreground">{children}</p>;


// Nothing here can be undone, and the rows are close together, so the
// destructive actions ask first and name who they are about.
export const Danger = ({ label, question, onConfirm, disabled, busy }) => (
  <Confirm size="sm" variant="quiet" label={busy ? "Working…" : label} question={question} yes="Yes" disabled={disabled}
    onConfirm={(close) => { close(); onConfirm(); }} />
);

export function Failed({ error, onRetry }) {
  return (
    <Card variant="outline" className="gap-3">
      <ErrorText error={error} />
      <div>
        <Button shape="rounded" size="sm" variant="quiet" onClick={onRetry}>Try again</Button>
      </div>
    </Card>
  );
}
