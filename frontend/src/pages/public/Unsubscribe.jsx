// /unsubscribe/:code: stop party news for the contact this link came with.
import { useParams } from "react-router-dom";
import { useUnsubscribe } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import PageHead from "./PageHead";

export default function Unsubscribe() {
  const { code } = useParams();
  const unsubscribe = useUnsubscribe(code);
  return (
    <div className="site-container py-12">
      <PageHead title="Unsubscribe" />
      <Card className="max-w-[620px]">
        {unsubscribe.data ? (
          <p role="status" className="text-base">{unsubscribe.data.message}</p>
        ) : (
          <>
            <p className="text-base">Stop party news by SMS or email for the contact this link came with.</p>
            {unsubscribe.error ? <p role="alert" className="text-small font-semibold text-destructive">{unsubscribe.error.message}</p> : null}
            <Button className="self-start" disabled={unsubscribe.isPending} onClick={() => unsubscribe.mutate()}>Unsubscribe</Button>
          </>
        )}
      </Card>
    </div>
  );
}
