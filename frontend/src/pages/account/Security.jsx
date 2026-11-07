// /security: 2-step sign-in for any signed-in login, and where a login that needs it is sent.
import { Link } from "react-router-dom";
import { useMe } from "@/api/hooks";
import TwoStep from "@/components/TwoStep";
import { landingOf } from "@/lib/home";
import { useAuth } from "@/store/auth";

export default function Security() {
  useMe();
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const blocked = user?.two_step_needed;
  return (
    <section className="mx-auto flex w-full max-w-[640px] flex-col gap-6 px-4 py-12">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-[34px] font-extrabold tracking-[-0.02em]">Sign-in security</h1>
        <p className="text-muted-foreground">Signed in as <b className="text-ink">{user?.username}</b>.</p>
      </div>
      <TwoStep />
      {blocked
        ? <button type="button" onClick={logout} className="self-start cursor-pointer font-bold text-primary">Sign out</button>
        : <Link to={landingOf(user)} className="self-start font-bold">Continue</Link>}
    </section>
  );
}
