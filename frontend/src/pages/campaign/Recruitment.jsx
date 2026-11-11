// The party workspace's Recruitment page, for a coordinator: their link to the Join the Party
// form, its QR code, and how many applicants it has brought, by status.
import { useRecruitment, useReplaceRecruitment } from "@/api/hooks";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { LinkCard } from "./ShareLink";
import { LoadingText } from "@/components/ui/loading-text";
import { linkTo } from "@/lib/format";
import { SlottedHeader } from "@/components/layout/AppPage";

const STATUSES = [
  ["pending", "Waiting for a decision"],
  ["approved", "Approved"],
  ["rejected", "Not approved"],
  ["suspended", "Suspended"],
  ["withdrawn", "Withdrawn"],
];

export default function Recruitment() {
  const recruitment = useRecruitment();
  const replace = useReplaceRecruitment();
  const data = recruitment.data;
  const link = data ? linkTo(`/join-party?r=${data.code}`) : "";
  return (
    <div className="flex flex-col gap-6">
      <SlottedHeader title="Recruitment" sub="Share your link: everyone who applies through it is counted to you. Membership officers still decide each application." />
      {recruitment.isLoading ? <LoadingText /> : null}
      <ErrorText error={recruitment.error} />
      {data ? (
        <div className="flex flex-wrap items-start gap-6">
          <Card variant="outline" className="min-w-0 flex-[1_1_360px] gap-4">
            <CardTitle>Your link</CardTitle>
            <LinkCard url={link} qrTitle="Recruitment link QR code" replacing={replace.isPending} onReplace={() => replace.mutate()}
              note="Replacing it stops the old link and QR code from recruiting." />
            <ErrorText error={replace.error} className="text-small" />
          </Card>
          <Card variant="outline" className="min-w-0 flex-[1_1_300px] gap-3">
            <CardTitle>Applicants through your link</CardTitle>
            <ul className="flex flex-col">
              {STATUSES.map(([key, label]) => (
                <li key={key} className="flex items-center justify-between gap-3 border-t border-line-soft py-2.5">
                  <span>{label}</span>
                  <strong className="font-display text-[20px]">{data.by_status[key] ?? 0}</strong>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
