// The public page a volunteer's private link opens: stop volunteer contact, keep the membership.
import { useParty, useWithdrawVolunteer } from "../../api/hooks";
import { Button } from "../../components/ui";
import { partyColours } from "./colours";

export default function WithdrawVolunteer({ code }) {
  const party = useParty();
  const withdraw = useWithdrawVolunteer(code);
  return (
    <div className="join-shell" style={partyColours(party.data)}>
      <div className="join-card">
        <div className="join-heading">Stop volunteer contact</div>
        {withdraw.isSuccess ? (
          <div className="join-message-success">{withdraw.data.message}</div>
        ) : (
          <>
            <div className="join-note">
              This link stops the party contacting you about volunteering. Your membership stays
              as it is.
            </div>
            {withdraw.error && <div className="join-error">{withdraw.error.message}</div>}
            <Button tone="danger" disabled={withdraw.isPending} onClick={() => withdraw.mutate()} className="join-submit">
              {withdraw.isPending ? "Stopping…" : "Stop volunteer contact"}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
