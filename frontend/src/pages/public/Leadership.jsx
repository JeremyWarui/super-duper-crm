// /leadership: the party leader first and large, then every other published leader, in the party's order.
import { usePublicLeaders } from "@/api/hooks";
import { RichText } from "@/components/RichTextView";
import { Card } from "@/components/ui/card";
import { Photo } from "./story";
import { LoadingText } from "@/components/ui/loading-text";
import { ErrorText } from "@/components/ui/error-text";
import { PageHero } from "@/components/PageHead";
import { RuleHead } from "@/components/ui/typography";
import { StoryMeta } from "@/components/ui/typography";

function Leader({ leader }) {
  return (
    <Card className="gap-0 overflow-hidden p-0">
      <Photo url={leader.photo_url} className="aspect-[4/5] w-full" />
      <span className="flex flex-col gap-1.5 p-5">
        <strong className="text-[19px]">{leader.name}</strong>
        <StoryMeta category={leader.position} />
        {leader.bio ? <RichText html={leader.bio} className="text-ui leading-[1.55] text-text-2" /> : null}
      </span>
    </Card>
  );
}

export default function Leadership() {
  const leaders = usePublicLeaders();
  const [head, ...rest] = leaders.data || [];
  return (
    <>
      <PageHero crumbs={[{ label: "About", to: "/about" }, { label: "Leadership" }]} kicker="Who leads us" title="Leadership" lead="The officials elected by the party's members to lead it between conventions." />
      <div className="site-container flex flex-col gap-12 pt-14 pb-[72px]">
        {leaders.isLoading ? <LoadingText /> : null}
        {leaders.error ? <ErrorText error={leaders.error} /> : null}
        {leaders.isSuccess && !head ? <p className="text-muted-foreground">The party has not listed its leaders yet.</p> : null}
        {head ? (
          <Card className="flex-row flex-wrap gap-0 overflow-hidden p-0">
            <Photo url={head.photo_url} className="aspect-square min-w-0 flex-[1_1_320px]" />
            <span className="flex min-w-0 flex-[2_1_360px] flex-col justify-center gap-3 p-8">
              <span className="text-meta font-extrabold uppercase tracking-[0.1em] text-primary">{head.position}</span>
              <strong className="font-display text-[clamp(30px,3.6vw,44px)] leading-[1.05] font-extrabold">{head.name}</strong>
              {head.bio ? <RichText html={head.bio} className="max-w-[60ch] text-[18px] leading-[1.65] text-text-2" /> : null}
            </span>
          </Card>
        ) : null}
        {rest.length ? (
          <section aria-labelledby="team-h" className="flex flex-col gap-[18px]">
            <RuleHead id="team-h">National officials</RuleHead>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-5">
              {rest.map((l) => <Leader key={l.id} leader={l} />)}
            </div>
          </section>
        ) : null}
      </div>
    </>
  );
}
