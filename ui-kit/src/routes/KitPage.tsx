import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input, NativeSelect, Field } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SectionHead } from '@/components/ui/typography'

/** Visual check of every kit part at its mockup size. Open /kit. */
export function KitPage() {
  return (
    <div className="site-container flex flex-col gap-10 py-14">
      <SectionHead kicker="Kit" title="Components at mockup sizes" />
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="accent" size="lg">Join the party</Button>
        <Button variant="outline">Contribute</Button>
        <Button>Primary</Button>
        <Button variant="ink">Ink</Button>
        <Button variant="quiet" shape="rounded">App secondary</Button>
        <Button shape="rounded">App primary</Button>
        <Button variant="danger" shape="rounded">Delete on request</Button>
        <Button size="sm" variant="quiet">Small</Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge>Verified</Badge><Badge tone="warn">Pending</Badge><Badge tone="bad">Flagged</Badge><Badge tone="info">Opted out</Badge>
        <Badge kind="label" tone="primary">Statement</Badge><Badge kind="kicker" tone="tint">From the party</Badge><Badge kind="chip" tone="stone">#Topic</Badge>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
        <Field label="Website input (50px)"><Input size="lg" placeholder="07XX… or name@mail.com" /></Field>
        <Field label="App input (44px)"><Input placeholder="Search" /></Field>
        <Field label="County"><NativeSelect size="lg"><option>Choose a county</option></NativeSelect></Field>
      </div>
      <Tabs defaultValue="a"><TabsList><TabsTrigger value="a">Upcoming</TabsTrigger><TabsTrigger value="b">Past</TabsTrigger></TabsList></Tabs>
      <Tabs look="underline" defaultValue="all"><TabsList>{['All', 'Statements', 'Press releases', 'Counties'].map((t) => <TabsTrigger key={t} value={t === 'All' ? 'all' : t}>{t}</TabsTrigger>)}</TabsList></Tabs>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
        <Card><strong>Elevated (website)</strong><span className="text-muted-foreground">20px corners, soft shadow</span></Card>
        <div className="app-shell rounded-card p-4"><Card variant="outline"><strong>Outline (CRM)</strong><span className="text-muted-foreground">16px corners, #E9E9E5 border</span></Card></div>
        <Card variant="ink"><strong>Ink panel</strong><span className="text-on-dark-muted">Ink background</span></Card>
      </div>
    </div>
  )
}
