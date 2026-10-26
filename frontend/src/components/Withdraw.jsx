// The public page a supporter's private link opens: take their details off the register.
import { useWithdraw } from "../api/hooks";
import { Button } from "./ui";

export default function Withdraw({ code }) {
  const withdraw = useWithdraw(code);
  return (
    <div className="join-shell">
      <div className="join-card">
        <div className="join-heading">Take your details off the register</div>
        {withdraw.isSuccess ? (
          <div className="join-message-success">{withdraw.data.message}</div>
        ) : (
          <>
            <div className="join-note">
              This removes the name and phone number you gave when you signed up. The campaign will
              no longer have them or contact you.
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
