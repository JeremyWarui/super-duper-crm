// The public page a volunteer's private link opens: stop volunteer contact, keep the membership.
import { useSite, useWithdrawVolunteer } from "@/api/hooks";
import LinkAction from "@/components/LinkAction";
import { partyColours } from "./colours";

export default function WithdrawVolunteer({ code }) {
  const party = useSite();
  return (
    <LinkAction
      action={useWithdrawVolunteer(code)}
      style={partyColours(party.data)}
      heading="Stop volunteer contact"
      note="This link stops the party contacting you about volunteering. Your membership stays as it is."
      label="Stop volunteer contact"
      busyLabel="Stopping…"
    />
  );
}
