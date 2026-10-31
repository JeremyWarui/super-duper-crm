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
        <div className="join-heading">Withdraw from the party</div>
        {withdraw.isSuccess ? (
          <div className="join-message-success">{withdraw.data.message}</div>
        ) : (
          <>
            <div className="join-note">
              This withdraws your application or membership, and the party will not contact you
              about it. The party keeps a record that you withdrew; to have your details erased,
              contact the party.
            </div>
            {withdraw.error && <div className="join-error">{withdraw.error.message}</div>}
            <Button tone="danger" disabled={withdraw.isPending} onClick={() => withdraw.mutate()} className="join-submit">
              {withdraw.isPending ? "Withdrawing…" : "Withdraw"}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
