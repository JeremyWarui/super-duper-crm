// The public page a supporter's private link opens: take their details off the register.
import { useWithdraw } from "../api/hooks";

const C = { ink: "#171C1F", paper: "#E9EBE6", panel: "#FFFFFF", green: "#0B6B3A", red: "#B4231F", sub: "#5C655F" };

export default function Withdraw({ code }) {
  const withdraw = useWithdraw(code);
  return (
    <div style={{ minHeight: "100vh", background: C.paper, display: "flex", justifyContent: "center", padding: "6vh 16px", fontFamily: "Inter, system-ui, sans-serif", color: C.ink }}>
      <div style={{ background: C.panel, borderRadius: 16, padding: 24, width: "100%", maxWidth: 420, alignSelf: "flex-start" }}>
        <div style={{ fontSize: 22, fontWeight: 700 }}>Take your details off the register</div>
        {withdraw.isSuccess ? (
          <div style={{ marginTop: 16, fontSize: 16, color: C.green }}>{withdraw.data.message}</div>
        ) : (
          <>
            <div style={{ marginTop: 10, fontSize: 14, color: C.sub, lineHeight: 1.5 }}>
              This removes the name and phone number you gave when you signed up. The campaign will
              no longer have them or contact you.
            </div>
            {withdraw.error && <div style={{ color: C.red, fontSize: 13, marginTop: 10 }}>{withdraw.error.message}</div>}
            <button disabled={withdraw.isPending} onClick={() => withdraw.mutate()}
              style={{ marginTop: 20, width: "100%", padding: "14px", borderRadius: 10, border: "none", fontSize: 16, fontWeight: 600, color: "var(--color-text-on-primary)", background: C.red, cursor: "pointer" }}>
              {withdraw.isPending ? "Removing…" : "Remove my details"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
