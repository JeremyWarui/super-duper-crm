// The party workspace's Recruitment page, for a coordinator: their link to the Join the Party
// form, its QR code, and how many applicants it has brought, by status.
import { QRCodeSVG } from "qrcode.react";
import { useRecruitment, useReplaceRecruitment } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { useClipboard } from "../../lib/useClipboard";
import { LoadingText } from "@/components/ui/loading-text";
import { linkTo } from "@/lib/format";

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
  const { copied, copy } = useClipboard();
  const data = recruitment.data;
  const link = data ? linkTo(`/join-party?r=${data.code}`) : "";
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-display text-h2-app font-extrabold tracking-[-0.02em]">Recruitment</h1>
        <p className="text-ui text-muted-foreground">Share your link: everyone who applies through it is counted to you. Membership officers still decide each application.</p>
      </div>
      {recruitment.isLoading ? <LoadingText /> : null}
      <ErrorText error={recruitment.error} />
      {data ? (
        <div className="flex flex-wrap items-start gap-6">
          <Card variant="outline" className="min-w-0 flex-[1_1_360px] gap-4">
            <CardTitle>Your link</CardTitle>
            <a href={link} className="break-all font-semibold">{link}</a>
            <div className="self-start rounded-xl border border-line bg-white p-3">
              <QRCodeSVG value={link} size={176} title="Recruitment link QR code" />
            </div>
            <div className="flex flex-wrap gap-2.5">
              <Button shape="rounded" variant="outline" onClick={() => copy(link)}>{copied ? "Copied" : "Copy link"}</Button>
              <Button shape="rounded" variant="quiet" disabled={replace.isPending} onClick={() => replace.mutate()}>Replace link</Button>
            </div>
            <p className="text-small text-muted-foreground">Replacing it stops the old link and QR code from recruiting.</p>
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
