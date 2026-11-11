import { QRCodeSVG } from "qrcode.react";
import { Button } from "@/components/ui/button";
import { useClipboard } from "@/lib/useClipboard";

// Copy a sign-up link, or send it on WhatsApp with a line saying what it is for.
export default function ShareLink({ link, message }) {
  const { copied, copy } = useClipboard();
  const whatsapp = `https://wa.me/?text=${encodeURIComponent(`${message} ${link}`)}`;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button shape="rounded" variant="quiet" onClick={() => copy(link)}>{copied ? "Copied" : "Copy link"}</Button>
      <Button asChild shape="rounded" variant="outline"><a href={whatsapp} target="_blank" rel="noreferrer">Share on WhatsApp</a></Button>
      {copied === false && <span className="text-small text-muted-foreground">This browser blocked copying; select the link above instead.</span>}
    </div>
  );
}

/** The printable sign-up block: `title`, the QR code for `link`, and the link written out. */
export function QrPrint({ title, link }) {
  return (
    <div className="qr-print flex flex-col items-center gap-3 text-center">
      <div className="text-lead font-semibold">{title}</div>
      <QRCodeSVG value={link} size={220} marginSize={2} title={`Sign-up link for ${title}`} />
      <div className="break-all text-small text-muted-foreground">{link}</div>
    </div>
  );
}

/** A standing link with its QR code and Copy; with `onReplace`, a Replace button and what replacing does. */
export function LinkCard({ url, qrTitle, onReplace, replacing, note }) {
  const { copied, copy } = useClipboard();
  return (
    <div className="flex flex-wrap items-start gap-5">
      <div className="rounded-xl border border-line bg-white p-3"><QRCodeSVG value={url} size={132} title={qrTitle} /></div>
      <div className="flex min-w-0 flex-[1_1_220px] flex-col gap-3">
        <a href={url} className="break-all font-semibold">{url}</a>
        <div className="flex flex-wrap gap-2">
          <Button shape="rounded" variant="quiet" size="sm" onClick={() => copy(url)}>{copied ? "Copied" : "Copy link"}</Button>
          {onReplace && <Button shape="rounded" variant="ghost" size="sm" disabled={replacing} onClick={onReplace}>Replace link</Button>}
        </div>
        {onReplace && <p className="text-small text-muted-foreground">{note}</p>}
      </div>
    </div>
  );
}
