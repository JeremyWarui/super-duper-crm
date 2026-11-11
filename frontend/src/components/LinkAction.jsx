import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import PageHead from "./PageHead";

/** The page a private link opens: a note and one button that acts on the link, then the server's reply. `action` is the mutation, run with `arg`; `variant` styles the button. */
export default function LinkAction({ action, arg, heading, note, label, busyLabel, variant = "danger", style }) {
  return (
    <div className="site-container py-12" style={style}>
      <PageHead title={heading} />
      <Card className="max-w-[620px]">
        {action.isSuccess ? (
          <p role="status" className="text-base">{action.data.message}</p>
        ) : (
          <>
            <p className="text-base">{note}</p>
            <ErrorText error={action.error} className="text-small" />
            <Button variant={variant} className="self-start" disabled={action.isPending} onClick={() => action.mutate(arg)}>
              {action.isPending ? busyLabel : label}
            </Button>
          </>
        )}
      </Card>
    </div>
  );
}
