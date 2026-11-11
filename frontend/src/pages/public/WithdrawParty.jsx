// The public page an applicant's private link opens: take their details off the party register.
import { useSite, useWithdrawParty } from "@/api/hooks";
import LinkAction from "@/components/LinkAction";
import { partyColours } from "./colours";

export default function WithdrawParty({ code }) {
  const party = useSite();
  return (
    <LinkAction
      action={useWithdrawParty(code)}
      style={partyColours(party.data)}
      heading="Withdraw from the party"
      note="This link withdraws the application or membership it came with, if that application put your number on the register. The party keeps the record with the status withdrawn; to have your details erased, contact the party."
      label="Withdraw"
      busyLabel="Withdrawing…"
    />
  );
}
