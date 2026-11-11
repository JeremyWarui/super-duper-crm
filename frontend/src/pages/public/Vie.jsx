// /vie: how to become one of the party's aspirants, step by step, and whom to call.
import { Link } from "react-router-dom";
import { useNominationNotice, useParty, useSite } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Crumbs } from "@/components/ui/typography";

import { SEAT_LABEL } from "@/lib/labels";
import { formatDay, formatKES, listItems } from "@/lib/format";


// The published nominations timetable: open now, or the next to open.
function Timetable() {
  const notice = useNominationNotice().data;
  if (!notice) return null;
  return (
    <Card aria-labelledby="timetable-h" asChild className="gap-4 p-6">
      <section>
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="timetable-h" className="font-display text-[26px] font-extrabold">{notice.title}</h2>
          <Badge tone={notice.open ? "ok" : "info"}>{notice.open ? "Applications open" : "Opens soon"}</Badge>
        </div>
        <p className="text-[17px]">Applications from <strong>{formatDay(notice.opens_on)}</strong> to <strong>{formatDay(notice.closes_on)}</strong>.</p>
        <table className="w-full max-w-[480px] text-left">
          <thead><tr className="text-small text-muted-foreground"><th className="py-1 font-semibold">Seat</th><th className="py-1 text-right font-semibold">Nomination fee</th></tr></thead>
          <tbody>
            {notice.seats.map((s) => (
              <tr key={s.seat} className="border-t border-line"><td className="py-2 font-semibold">{SEAT_LABEL[s.seat]}</td><td className="py-2 text-right tabular-nums">{s.fee_kes ? formatKES(s.fee_kes) : "No fee"}</td></tr>
            ))}
          </tbody>
        </table>
        {notice.requirements && (
          <div className="flex flex-col gap-1">
            <h3 className="font-bold">Requirements</h3>
            <p className="whitespace-pre-line text-[16px] leading-[1.6]">{notice.requirements}</p>
          </div>
        )}
        {notice.open && <Button asChild className="self-start"><Link to="/account">Apply from your member account</Link></Button>}
      </section>
    </Card>
  );
}

export default function Vie() {
  const party = { ...useSite().data, ...useParty().data };
  const list = listItems(party.aspirant_steps);
  const office = [
    ["Office", party.address],
    ["Phone", party.contact_phone, party.contact_phone && `tel:${party.contact_phone.replace(/\s+/g, "")}`],
    ["Email", party.contact_email, party.contact_email && `mailto:${party.contact_email}`],
  ].filter(([, value]) => value);
  return (
    <>
      <section className="bg-primary text-white">
        <div className="site-container flex flex-col gap-5 py-14">
          <Crumbs onDark items={[{ label: "Home", to: "/" }, { label: "Vie with us" }]} />
          <p className="text-ui font-bold uppercase tracking-[0.12em] text-accent">Seeking a seat?</p>
          <h1 className="font-display text-[clamp(40px,5vw,64px)] leading-none font-extrabold tracking-[-0.03em]">Vie with us</h1>
          <p className="max-w-[640px] text-[18px] leading-[1.6] text-[#CFE0D5]">
            Run for MCA, MP, Governor, Senator or Women Rep on the {party.short_name || party.name || "party"} ticket. Here is how to become an aspirant.
          </p>
        </div>
      </section>
      <div className="site-container flex flex-wrap items-start gap-10 pt-14 pb-[72px]">
        <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-10">
        <Timetable />
        <section aria-labelledby="steps-h" className="flex min-w-0 flex-col gap-5">
          <h2 id="steps-h" className="rule-top font-display text-[32px] font-extrabold">How to become an aspirant</h2>
          {list.length ? (
            <ol className="flex flex-col gap-3.5">
              {list.map((step, n) => (
                <Card key={n} asChild className="flex-row items-start gap-4 p-5">
                  <li>
                    <span aria-hidden className="flex size-11 flex-none items-center justify-center rounded-full bg-primary-tint font-display text-[20px] font-extrabold text-primary">{n + 1}</span>
                    <span className="self-center text-[17px] leading-[1.55]">{step}</span>
                  </li>
                </Card>
              ))}
            </ol>
          ) : (
            <p className="text-muted-foreground">The party office will publish the steps here. Until then, call or write to the office.</p>
          )}
        </section>
        </div>
        <aside className="flex min-w-0 flex-[1_1_300px] flex-col gap-5">
          <Card variant="ink">
            <h2 className="text-[20px] font-bold">Talk to the party office</h2>
            {office.length ? (
              <dl className="flex flex-col gap-2.5">
                {office.map(([label, value, href]) => (
                  <div key={label} className="flex flex-col">
                    <dt className="text-small text-on-dark-muted">{label}</dt>
                    <dd className="font-semibold">{href ? <a href={href} className="inline-flex min-h-11 items-center text-accent hover:text-accent">{value}</a> : value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-on-dark-muted">The office's contacts will be published here.</p>
            )}
          </Card>
          <Card variant="panel" className="bg-primary-tint">
            <h2 className="text-[18px] font-bold">Not a member yet?</h2>
            <p className="text-[15px] text-text-2">Only party members can vie. Join first, then sign in to follow your application.</p>
            <span className="flex flex-wrap gap-2.5">
              <Button asChild><Link to="/join-party">Join the party</Link></Button>
              <Button asChild variant="quiet"><Link to="/signin">Sign in</Link></Button>
            </span>
          </Card>
        </aside>
      </div>
    </>
  );
}
