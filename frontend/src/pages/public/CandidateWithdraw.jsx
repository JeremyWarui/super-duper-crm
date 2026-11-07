// /candidates/volunteer/withdraw/:code: take a volunteer off a candidate's campaign list.
import { useParams } from "react-router-dom";
import { useCandidateWithdraw } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import PageHead from "./PageHead";
import { ErrorText } from "@/components/ui/error-text";

export default function CandidateWithdraw() {
  const { code } = useParams();
  const withdraw = useCandidateWithdraw();
  return (
    <div className="site-container py-12">
      <PageHead title="Stop volunteering" />
      <Card className="max-w-[620px]">
        {withdraw.data ? (
          <p role="status" className="text-base">{withdraw.data.message}</p>
        ) : (
          <>
            <p className="text-base">Take your details off the campaign's volunteer list this link came with.</p>
            <ErrorText error={withdraw.error} className="text-small" />
            <Button className="self-start" disabled={withdraw.isPending} onClick={() => withdraw.mutate(code)}>Remove my details</Button>
          </>
        )}
      </Card>
    </div>
  );
}
