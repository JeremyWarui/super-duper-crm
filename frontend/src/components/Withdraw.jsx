// The public page a supporter's private link opens: take their details off the register.
import { useWithdraw } from "@/api/hooks";
import LinkAction from "./LinkAction";

export default function Withdraw({ code }) {
  return (
    <LinkAction
      action={useWithdraw(code)}
      heading="Take your details off the register"
      note="This removes the name and phone number you gave when you signed up. The campaign will no longer have them or contact you."
      label="Remove my details"
      busyLabel="Removing…"
    />
  );
}
