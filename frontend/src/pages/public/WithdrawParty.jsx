// The public page an applicant's private link opens: take their details off the party register.
import { useParty, useWithdrawParty } from "../../api/hooks";
import { Button } from "../../components/ui";
import { partyColours } from "./colours";

export default function WithdrawParty({ code }) {
  const party = useParty();
  const withdraw = useWithdrawParty(code);
  return (
    <div className="join-shell" style={partyColours(party.data)}>
      <div className="join-card">
        <div className="join-heading">Take your details off the party register</div>
        {withdraw.isSuccess ? (
          <div className="join-message-success">{withdraw.data.message}</div>
        ) : (
          <>
            <div className="join-note">
              This removes the name and phone number you gave when you applied. The party will no
              longer have them or contact you.
            </div>
            {withdraw.error && <div className="join-error">{withdraw.error.message}</div>}
            <Button tone="danger" disabled={withdraw.isPending} onClick={() => withdraw.mutate()} className="join-submit">
              {withdraw.isPending ? "Removing…" : "Remove my details"}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
