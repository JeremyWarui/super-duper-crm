// /signin/where: a staff or campaign login linked to an approved member picks where to go.
import { Link } from "react-router-dom";
import { Logo } from "@/components/layout/Logo";
import { homeOf } from "@/lib/home";
import { useAuth } from "@/store/auth";
import { PARTY_ROLE_LABEL } from "@/lib/labels";

const ROLE = { candidate: "Candidate team", manager: "Candidate team", mobilizer: "Mobilizer" };

/** The places a login's roles open, each a card. */
export function placesOf(user) {
  const home = homeOf(user);
  const work =
    home === "/campaign"
      ? { title: "Campaign workspace", desc: "Targets, events, mobilizers and supporters", role: ROLE[user.role] || "Campaign", initial: "W", box: "bg-ink text-accent" }
      : {
          title: user.is_superuser ? "Console" : "Party CRM",
          desc: "Members, volunteers, aspirants and website, as your roles allow",
          role: user.is_superuser ? "Party super admin" : (user.party_roles || []).map((r) => PARTY_ROLE_LABEL[r] || r).join(", "),
          initial: "C",
          box: "bg-primary text-white",
        };
  return [
    { to: "/account", title: "My membership", desc: "Member card, volunteering, party events and my data", role: "Member", initial: "M", box: "bg-primary-tint text-primary" },
    { to: home, ...work },
  ];
}

export default function Chooser() {
  const user = useAuth((s) => s.user);
  const first = (user?.full_name || "").split(" ")[0];
  return (
    <div className="flex min-h-dvh justify-center bg-background px-6 py-14">
      <div className="flex w-full max-w-[760px] flex-col gap-6">
        <Logo size="md" />
        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-[clamp(32px,4vw,44px)] font-extrabold tracking-[-0.02em]">{first ? `Karibu, ${first}. Where to?` : "Karibu. Where to?"}</h1>
          <p className="text-base text-text-2">Your account has more than one role. You'll only see the places your roles allow.</p>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-3.5">
          {placesOf(user).map((p) => (
            <Link key={p.to} to={p.to} className="flex items-start gap-4 rounded-photo border-[1.5px] border-line-2 bg-white p-5 text-ink no-underline hover:border-primary hover:text-ink">
              <span aria-hidden className={`flex size-12 flex-none items-center justify-center rounded-[8px] font-display text-[20px] font-extrabold ${p.box}`}>{p.initial}</span>
              <span className="flex min-w-0 flex-col gap-1">
                <strong className="text-[18px]">{p.title}</strong>
                <span className="text-ui text-muted-foreground">{p.desc}</span>
                <span className="pt-1 text-meta font-bold uppercase tracking-[0.06em] text-primary">{p.role}</span>
              </span>
            </Link>
          ))}
        </div>
        <p className="text-small text-muted-foreground">Switch any time from the menu at the top of each area.</p>
      </div>
    </div>
  );
}
