import * as React from 'react'
import { Button } from '@/components/ui/button'
import { Card, KpiValue } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { FilterPills } from '@/components/ui/tabs'
import { Table, THead, TBody, TR, TH, TD, RowButton } from '@/components/ui/table'
import { AppPage } from '@/components/layout/AppPage'

const rows = [
  { id: 1, name: '[Applicant 01]', county: '[County]', via: 'Website', fee: 'Paid', status: 'Pending' },
  { id: 2, name: '[Applicant 02]', county: '[County]', via: 'Field app', fee: 'Paid', status: 'Flagged' },
  { id: 3, name: '[Applicant 03]', county: '[County]', via: 'USSD', fee: 'Unpaid', status: 'Pending' },
  { id: 4, name: '[Applicant 04]', county: '[County]', via: 'Website', fee: 'Paid', status: 'Verified' },
] as const
const tone = { Pending: 'warn', Flagged: 'bad', Verified: 'ok' } as const

/** Demo CRM screen: sticky top bar + page header with actions, KPI tiles, table + detail card. */
export function MembersPage() {
  const [f, setF] = React.useState<'All' | 'Pending' | 'Flagged' | 'Verified'>('All')
  const [sel, setSel] = React.useState(2)
  const list = rows.filter((r) => f === 'All' || r.status === f)
  const s = rows.find((r) => r.id === sel)!
  return (
    <AppPage
      crumb="Members"
      context="Verification queue · [County] scope"
      title="Membership verification"
      actions={<>
        <FilterPills label="Filter" options={['All', 'Pending', 'Flagged', 'Verified'] as const} value={f} onChange={setF} />
        <Button variant="quiet" shape="rounded">Export</Button>
        <Button shape="rounded">Verify selected</Button>
      </>}
    >
      <section aria-label="Summary" className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-4">
        {[['Waiting', '[000]'], ['Flagged', '[00]'], ['Verified this week', '[0,000]'], ['Total members', '[00,000]']].map(([l, v]) => (
          <Card key={l} variant="tile"><span className="text-ui font-semibold text-muted-foreground">{l}</span><KpiValue>{v}</KpiValue></Card>
        ))}
      </section>
      <div className="flex flex-wrap items-start gap-6">
        <Card variant="outline" className="min-w-0 flex-[3_1_520px] gap-3">
          <Table>
            <THead><tr><TH>Applicant</TH><TH>County</TH><TH>Came in via</TH><TH>Fee</TH><TH>Status</TH></tr></THead>
            <TBody>
              {list.map((r) => (
                <TR key={r.id} selected={r.id === sel}>
                  <TD><RowButton onClick={() => setSel(r.id)}>{r.name}</RowButton></TD>
                  <TD>{r.county}</TD><TD>{r.via}</TD><TD>{r.fee}</TD>
                  <TD><Badge tone={tone[r.status]}>{r.status}</Badge></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
        <Card asChild variant="outline" className="min-w-0 flex-[2_1_320px] gap-3.5"><aside aria-label="Applicant details">
          <h2 className="text-card-title font-bold">{s.name}</h2>
          <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3.5 gap-y-2.5 text-ui">
            <dt className="text-muted-foreground">ID check</dt><dd className="m-0 font-semibold">[Matched IPRS]</dd>
            <dt className="text-muted-foreground">Other parties</dt><dd className="m-0 font-semibold">{s.status === 'Flagged' ? 'Listed with [Party X]' : 'None found'}</dd>
            <dt className="text-muted-foreground">Fee</dt><dd className="m-0 font-semibold">{s.fee}</dd>
          </dl>
          {s.status === 'Flagged' ? <p className="rounded-md bg-bad p-3 text-ui text-[#7A1A12]">Appears on another party's register. Ask the applicant for a resignation letter before verifying.</p> : null}
          <Card variant="tinted"><span className="text-small text-muted-foreground">Consent</span><span className="text-ui font-semibold">Privacy notice v[0.0] · [date] · Website</span></Card>
          <div className="flex flex-wrap gap-2"><Button shape="rounded">Verify</Button><Button variant="danger" shape="rounded">Reject</Button></div>
        </aside></Card>
      </div>
    </AppPage>
  )
}
