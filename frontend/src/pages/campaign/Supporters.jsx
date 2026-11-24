import { useState } from "react";
import { rowsOf, useErase, usePlaceSupporter, useSupporterCounts, useSupporterPages, useTextWithdrawalLink, useWithdrawalLink } from "@/api/hooks";
import EraseButton from "@/components/EraseButton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyRow, Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { FilterPills } from "@/components/ui/tabs";
import { useCopy } from "@/copy";
import { formatNumber as fmt } from "@/lib/format";
import { ErrorText } from "@/components/ui/error-text";
import { StatTiles } from "@/components/ui/stat-tiles";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";
import { LoadMore } from "@/components/ui/load-more";
import { useDebounced } from "@/lib/useDebounced";

import { SUPPORT_LEVELS } from "@/lib/labels";
import { isLead, unitOf, useTargetedCentres } from "./helpers";
const TONE = { supporter: "ok", undecided: "warn", opposed: "bad" };

// A supporter's private withdrawal link, to read out or text to them.
function WithdrawalLink({ campaign, supporter, onClose }) {
  const link = useWithdrawalLink(campaign.id, supporter.id);
  const text = useTextWithdrawalLink(campaign.id);
  return (
    <div role="region" aria-label={`Withdrawal link for ${supporter.full_name}`} className="grid gap-2 rounded-lg border border-line bg-muted p-3">
      <p className="text-ui font-semibold">Withdrawal link for {supporter.full_name}</p>
      <p className="text-small text-muted-foreground">Opening it removes their details from the register for good.</p>
      <ErrorText error={link.error} />
      {link.data ? <Input readOnly aria-label="Withdrawal link" value={link.data.url} onFocus={(e) => e.target.select()} /> : null}
      <div className="flex flex-wrap items-center gap-2">
        {link.data?.can_text && !campaign.closed_at ? (
          <Button size="sm" loading={text.isPending} disabled={text.isSuccess} onClick={() => text.mutate(supporter.id)}>
            {text.isSuccess ? "Texted" : text.isPending ? "Texting…" : "Text it to them"}
          </Button>
        ) : null}
        <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
      </div>
      <ErrorText error={text.error} />
    </div>
  );
}

function Summary({ counts }) {
  const tiles = [["On the register", counts.total], ["Supporters", counts.supporters], ["Undecided", counts.undecided], ["Consent missing", counts.consent_missing]];
  return (
    <StatTiles min={150} tiles={tiles.map(([label, value]) => [label, fmt(value)])} />
  );
}

// How many rows a level filter covers, from the counts.
const countFor = (counts, level) => ({
  "": counts.total,
  supporter: counts.supporters,
  undecided: counts.undecided,
  opposed: counts.total - counts.supporters - counts.undecided,
})[level];

// The contact register, private to the campaign team; in an MCA race each one sits at a centre.
export default function Supporters({ campaign, role, mine, onModal }) {
  const copy = useCopy();
  const centreWard = unitOf(campaign).byCentre ? campaign.ward : null;
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim(), 300);
  const pages = useSupporterPages(campaign.id, { q, support_level: filter });
  const counts = useSupporterCounts(campaign.id, q);
  const { centres, all: allCentres, targeted, ready } = useTargetedCentres(campaign.id, centreWard);
  const showCentre = centreWard && ready;
  const centreName = (id) => allCentres.find((c) => c.id === id)?.name;
  const place = usePlaceSupporter();
  const erase = useErase(campaign.id, "supporters");
  const keeper = !mine && isLead(role);
  const [linkFor, setLinkFor] = useState(null);
  const shown = rowsOf(pages.data);
  const action = keeper ? <Button onClick={() => onModal({ type: "link" })}>Sign-up link</Button> : null;
  return (
    <>
      <SlottedHeader context={mine ? "My work" : "Field"} title={mine ? "My contacts" : "Contacts"} sub={copy.supportersSub} actions={action} />
      {pages.isLoading && <LoadingText />}
      <ErrorText error={pages.error || counts.error} />
      {pages.data && (
        <>
          {counts.data && <Summary counts={counts.data} />}
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-label="Contact list">
            <div className="flex flex-wrap items-center gap-3">
              <FilterPills label="Support" options={[["", "All"], ...SUPPORT_LEVELS]} value={filter} onChange={setFilter} />
              <Input type="search" aria-label="Search contacts" placeholder="Search by name or phone" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
            </div>
            <Table stack minWidth={560}>
              <THead><TR><TH>Name</TH><TH>Phone</TH><TH>Support</TH>{showCentre && <TH>Centre</TH>}<TH>Consent</TH>{keeper && <TH srOnly>Personal data</TH>}</TR></THead>
              <TBody>
                {shown.map((s) => (
                  <TR key={s.id}>
                    <TD className="font-semibold">{s.full_name}</TD>
                    <TD className="text-muted-foreground tabular-nums">{s.phone}</TD>
                    <TD><Badge tone={TONE[s.support_level]} className="capitalize">{s.support_level}</Badge></TD>
                    {showCentre && (
                      <TD>{targeted.has(s.registration_centre) ? centreName(s.registration_centre) || "Unknown centre" : (
                        <select aria-label={`Centre for ${s.full_name}`} value="" disabled={place.isPending} onChange={(e) => place.mutate({ id: s.id, registration_centre: e.target.value })}
                          className="h-10 max-w-full rounded-[10px] border-[1.5px] border-line-control bg-white px-2.5 text-ui max-sm:h-11">
                          <option value="">{s.registration_centre ? `${centreName(s.registration_centre) || "Centre"} has no target` : "Needs a centre"}</option>
                          {centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                      )}</TD>
                    )}
                    <TD>{s.erased_at ? <Badge tone="stone">Erased</Badge> : s.consent_given ? <span className="inline-flex flex-wrap gap-1"><Badge tone="ok">Given</Badge>{s.sms_consent && <Badge tone="info">SMS</Badge>}</span> : <Badge tone="bad">Missing</Badge>}</TD>
                    {keeper && (
                      <TD align="right">
                        {!s.erased_at && (
                          <span className="inline-flex flex-wrap justify-end gap-2">
                            <Button size="sm" variant="quiet" onClick={() => setLinkFor(s)}>Withdrawal link</Button>
                            <EraseButton name={s.full_name} pending={erase.isPending} onErase={(done) => erase.mutate(s.id, { onSuccess: () => { done(); setLinkFor(null); } })} />
                          </span>
                        )}
                      </TD>
                    )}
                  </TR>
                ))}
                {shown.length === 0 && <EmptyRow>{q ? "No contact matches." : "None yet."}</EmptyRow>}
              </TBody>
            </Table>
            <LoadMore shown={shown.length} total={counts.data && !pages.isPlaceholderData && !counts.isPlaceholderData ? countFor(counts.data, filter) : undefined} noun="contacts" hasMore={!!pages.hasNextPage} loading={pages.isFetchingNextPage} onMore={() => pages.fetchNextPage()} />
            <ErrorText error={place.error} />
            <ErrorText error={erase.error} />
            {linkFor && <WithdrawalLink key={linkFor.id} campaign={campaign} supporter={linkFor} onClose={() => setLinkFor(null)} />}
          </Card>
        </>
      )}
    </>
  );
}
