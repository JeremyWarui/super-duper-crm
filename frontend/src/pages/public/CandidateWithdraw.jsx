// /candidates/volunteer/withdraw/:code: take a volunteer off a candidate's campaign list.
import { useParams } from "react-router-dom";
import { useCandidateWithdraw } from "@/api/hooks";
import LinkAction from "@/components/LinkAction";

export default function CandidateWithdraw() {
  const { code } = useParams();
  return (
    <LinkAction
      action={useCandidateWithdraw()}
      arg={code}
      heading="Stop volunteering"
      note="Take your details off the campaign's volunteer list this link came with."
      label="Remove my details"
      busyLabel="Removing…"
    />
  );
}
